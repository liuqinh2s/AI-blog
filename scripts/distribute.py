#!/usr/bin/env python3
"""
多平台内容分发脚本
将 digests/ 中的期刊内容，通过 AI 改编后分发到多个社交平台。

支持平台：
- 微信公众号（WeChat Official Account）— 官方 API 创建草稿
- 微博（Weibo）— 官方开放 API
- 推特/X（Twitter/X）— 官方 API v2
- 小红书（Xiaohongshu）— 生成适配内容，手动/半自动发布
- 知识星球（Zsxq）— 非官方 API

使用方式：
    python3 scripts/distribute.py                    # 分发最新的期刊
    python3 scripts/distribute.py --type daily       # 只分发日报
    python3 scripts/distribute.py --type weekly      # 只分发周刊
    python3 scripts/distribute.py --file digests/weekly/2025-W01.md  # 分发指定文件
    python3 scripts/distribute.py --platforms weibo,twitter  # 只分发到指定平台
    python3 scripts/distribute.py --dry-run          # 预览模式，不实际发布
"""

from __future__ import annotations

import os
import re
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx

# ─── 环境配置 ──────────────────────────────────────────────────────

def load_dotenv():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

load_dotenv()

# DeepSeek AI
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# 微信公众号
WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_SECRET = os.environ.get("WECHAT_SECRET", "")

# 微博
WEIBO_ACCESS_TOKEN = os.environ.get("WEIBO_ACCESS_TOKEN", "")

# 推特/X
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET", "")

# 知识星球
ZSXQ_ACCESS_TOKEN = os.environ.get("ZSXQ_ACCESS_TOKEN", "")
ZSXQ_GROUP_ID = os.environ.get("ZSXQ_GROUP_ID", "")

# 项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIGESTS_DIR = PROJECT_ROOT / "digests"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DISTRIBUTE_STATE_FILE = PROJECT_ROOT / ".distribute_state.json"
DISTRIBUTE_OUTPUT_DIR = PROJECT_ROOT / "distribute_output"


# ─── 提示词加载 ────────────────────────────────────────────────────

def load_prompt(filename: str) -> str:
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        print(f"⚠️  提示词文件不存在: {prompt_path}")
        return ""
    return prompt_path.read_text(encoding="utf-8").strip()

DISTRIBUTE_SYSTEM_PROMPT = load_prompt("distribute_system.md")


# ─── AI 内容改编 ───────────────────────────────────────────────────

def call_deepseek(prompt: str, system_prompt: str = "") -> str:
    """调用 DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        print("⚠️  DEEPSEEK_API_KEY 未设置，跳过 AI 改编")
        return ""

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = httpx.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4000,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return ""


def adapt_content_for_platform(digest_content: str, platform: str) -> dict:
    """用 AI 将期刊内容改编为目标平台格式"""
    prompt = f"请将以下知识期刊改编为【{platform}】平台的发布内容：\n\n{digest_content}"
    raw = call_deepseek(prompt, DISTRIBUTE_SYSTEM_PROMPT)

    if not raw:
        return {}

    # 尝试解析 JSON
    try:
        # 清理可能的 markdown 代码块标记
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"⚠️  AI 返回内容无法解析为 JSON，使用原始文本")
        return {"title": "", "content": raw, "tags": []}


# ─── 分发状态管理 ───────────────────────────────────────────────────

def load_distribute_state() -> dict:
    if DISTRIBUTE_STATE_FILE.exists():
        return json.loads(DISTRIBUTE_STATE_FILE.read_text(encoding="utf-8"))
    return {"distributed": {}}


def save_distribute_state(state: dict):
    state["last_run"] = datetime.now().isoformat()
    DISTRIBUTE_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def content_hash(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]


# ─── 平台发布实现 ───────────────────────────────────────────────────

# --- 微信公众号 ---

def wechat_get_access_token() -> str:
    """获取微信公众号 access_token"""
    if not WECHAT_APPID or not WECHAT_SECRET:
        return ""
    try:
        resp = httpx.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": WECHAT_APPID,
                "secret": WECHAT_SECRET,
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" in data:
            return data["access_token"]
        print(f"⚠️  微信 access_token 获取失败: {data}")
        return ""
    except Exception as e:
        print(f"❌ 微信 API 调用失败: {e}")
        return ""


def publish_to_wechat(adapted: dict) -> bool:
    """发布到微信公众号（创建草稿）"""
    token = wechat_get_access_token()
    if not token:
        print("⚠️  微信公众号：未配置或 token 获取失败，跳过")
        return False

    title = adapted.get("title", "知识期刊")
    content = adapted.get("content", "")

    # 将 Markdown 转为简单 HTML（微信公众号草稿需要 HTML）
    html_content = markdown_to_simple_html(content)

    try:
        # 创建草稿
        resp = httpx.post(
            f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}",
            json={
                "articles": [
                    {
                        "title": title,
                        "author": "AI 知识期刊",
                        "content": html_content,
                        "digest": content[:120],
                        "content_source_url": "",
                        "need_open_comment": 1,
                    }
                ]
            },
            timeout=30,
        )
        data = resp.json()
        if "media_id" in data:
            print(f"  ✅ 微信公众号：草稿创建成功 (media_id: {data['media_id']})")
            print(f"     请登录公众号后台审核并发布")
            return True
        else:
            print(f"  ❌ 微信公众号：草稿创建失败: {data}")
            return False
    except Exception as e:
        print(f"  ❌ 微信公众号发布失败: {e}")
        return False


def markdown_to_simple_html(md: str) -> str:
    """简单的 Markdown → HTML 转换（用于微信公众号）"""
    lines = md.split("\n")
    html_lines = []
    for line in lines:
        # 标题
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        # 列表
        elif line.startswith("- "):
            html_lines.append(f"<p>• {line[2:]}</p>")
        elif re.match(r"^\d+\.\s", line):
            html_lines.append(f"<p>{line}</p>")
        # 引用
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{line[2:]}</blockquote>")
        # 粗体
        elif "**" in line:
            line = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f"<p>{line}</p>")
        # 空行
        elif not line.strip():
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)


# --- 微博 ---

def publish_to_weibo(adapted: dict) -> bool:
    """发布到微博"""
    if not WEIBO_ACCESS_TOKEN:
        print("⚠️  微博：未配置 access_token，跳过")
        return False

    content = adapted.get("content", "")
    tags = adapted.get("tags", [])

    # 微博内容拼接标签
    tag_str = " ".join(f"#{t}#" for t in tags)
    full_content = f"{content}\n\n{tag_str}".strip()

    # 微博字数限制
    if len(full_content) > 2000:
        full_content = full_content[:1997] + "..."

    try:
        resp = httpx.post(
            "https://api.weibo.com/2/statuses/share.json",
            data={
                "access_token": WEIBO_ACCESS_TOKEN,
                "status": full_content,
            },
            timeout=30,
        )
        data = resp.json()
        if "id" in data:
            print(f"  ✅ 微博：发布成功 (id: {data['id']})")
            return True
        else:
            print(f"  ❌ 微博：发布失败: {data}")
            return False
    except Exception as e:
        print(f"  ❌ 微博发布失败: {e}")
        return False


# --- 推特/X ---

def publish_to_twitter(adapted: dict) -> bool:
    """发布到推特/X（使用 OAuth 1.0a）"""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("⚠️  推特/X：未配置完整的 API 凭证，跳过")
        return False

    threads = adapted.get("thread", [])
    if not threads:
        # 如果没有 thread，用 content 作为单条推文
        content = adapted.get("content", "")
        tags = adapted.get("tags", [])
        tag_str = " ".join(f"#{t}" for t in tags)
        full = f"{content} {tag_str}".strip()
        if len(full) > 280:
            full = full[:277] + "..."
        threads = [full]

    try:
        # 使用 OAuth 1.0a 签名
        from urllib.parse import quote
        import hmac
        import base64
        import time
        import uuid

        previous_tweet_id = None
        for i, tweet_text in enumerate(threads):
            if len(tweet_text) > 280:
                tweet_text = tweet_text[:277] + "..."

            payload = {"text": tweet_text}
            if previous_tweet_id:
                payload["reply"] = {"in_reply_to_tweet_id": previous_tweet_id}

            # OAuth 1.0a 签名
            oauth_params = {
                "oauth_consumer_key": TWITTER_API_KEY,
                "oauth_nonce": uuid.uuid4().hex,
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_timestamp": str(int(time.time())),
                "oauth_token": TWITTER_ACCESS_TOKEN,
                "oauth_version": "1.0",
            }

            # 构建签名基字符串
            method = "POST"
            url = "https://api.twitter.com/2/tweets"
            param_str = "&".join(
                f"{quote(k, safe='')}={quote(v, safe='')}"
                for k, v in sorted(oauth_params.items())
            )
            base_string = f"{method}&{quote(url, safe='')}&{quote(param_str, safe='')}"
            signing_key = f"{quote(TWITTER_API_SECRET, safe='')}&{quote(TWITTER_ACCESS_SECRET, safe='')}"
            signature = base64.b64encode(
                hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
            ).decode()
            oauth_params["oauth_signature"] = signature

            auth_header = "OAuth " + ", ".join(
                f'{quote(k, safe="")}="{quote(v, safe="")}"'
                for k, v in sorted(oauth_params.items())
            )

            resp = httpx.post(
                url,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            data = resp.json()

            if "data" in data and "id" in data["data"]:
                previous_tweet_id = data["data"]["id"]
                print(f"  ✅ 推特/X：第 {i+1}/{len(threads)} 条发布成功")
            else:
                print(f"  ❌ 推特/X：第 {i+1} 条发布失败: {data}")
                return False

        print(f"  ✅ 推特/X：Thread 全部发布成功 ({len(threads)} 条)")
        return True

    except ImportError:
        print("  ❌ 推特/X：缺少依赖，请确保 Python 标准库可用")
        return False
    except Exception as e:
        print(f"  ❌ 推特/X 发布失败: {e}")
        return False


# --- 小红书 ---

def publish_to_xiaohongshu(adapted: dict, digest_file: str) -> bool:
    """
    小红书：生成适配内容保存到本地文件。
    小红书没有官方 API，自动发布属于灰色地带，
    因此采用「AI 生成内容 → 保存到文件 → 手动/半自动发布」的安全策略。
    """
    title = adapted.get("title", "知识分享")
    content = adapted.get("content", "")
    tags = adapted.get("tags", [])

    tag_str = " ".join(f"#{t}" for t in tags)
    full_content = f"{content}\n\n{tag_str}"

    # 保存到 distribute_output 目录
    DISTRIBUTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = DISTRIBUTE_OUTPUT_DIR / f"xiaohongshu_{date_str}.md"

    output_content = f"""# 小红书发布内容

> 来源: {digest_file}
> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 状态: 待发布

## 标题
{title}

## 正文
{full_content}

## 标签
{', '.join(tags)}

---
💡 发布方式：
1. 打开小红书 App 或网页版
2. 复制上方标题和正文
3. 粘贴发布即可
"""
    output_file.write_text(output_content, encoding="utf-8")
    print(f"  ✅ 小红书：内容已保存到 {output_file}")
    print(f"     请手动复制内容到小红书发布")
    return True


# --- 知识星球 ---

def publish_to_zsxq(adapted: dict) -> bool:
    """发布到知识星球"""
    if not ZSXQ_ACCESS_TOKEN or not ZSXQ_GROUP_ID:
        print("⚠️  知识星球：未配置 access_token 或 group_id，跳过")
        return False

    content = adapted.get("content", "")

    try:
        resp = httpx.post(
            f"https://api.zsxq.com/v2/groups/{ZSXQ_GROUP_ID}/topics",
            headers={
                "Authorization": f"Bearer {ZSXQ_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "req_data": {
                    "type": "talk",
                    "text": content,
                }
            },
            timeout=30,
        )
        data = resp.json()
        if data.get("succeeded"):
            topic_id = data.get("resp_data", {}).get("topic", {}).get("topic_id", "")
            print(f"  ✅ 知识星球：发布成功 (topic_id: {topic_id})")
            return True
        else:
            print(f"  ❌ 知识星球：发布失败: {data}")
            return False
    except Exception as e:
        print(f"  ❌ 知识星球发布失败: {e}")
        return False


# ─── 核心分发逻辑 ───────────────────────────────────────────────────

ALL_PLATFORMS = {
    "wechat": ("微信公众号", publish_to_wechat),
    "weibo": ("微博", publish_to_weibo),
    "twitter": ("推特/X", publish_to_twitter),
    "xiaohongshu": ("小红书", None),  # 特殊处理
    "zsxq": ("知识星球", publish_to_zsxq),
}

PLATFORM_NAMES = {
    "wechat": "微信公众号",
    "weibo": "微博",
    "twitter": "推特/X",
    "xiaohongshu": "小红书",
    "zsxq": "知识星球",
}


def find_latest_digest(digest_type: str = "") -> Path | None:
    """查找最新的期刊文件"""
    search_dirs = []
    if digest_type:
        d = DIGESTS_DIR / digest_type
        if d.exists():
            search_dirs.append(d)
    else:
        for sub in ["daily", "weekly", "monthly", "quarterly", "yearly"]:
            d = DIGESTS_DIR / sub
            if d.exists():
                search_dirs.append(d)

    latest_file = None
    latest_mtime = 0

    for d in search_dirs:
        for f in d.glob("*.md"):
            if f.name == "index.md":
                continue
            mtime = f.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = f

    return latest_file


def read_digest_content(digest_path: Path) -> str:
    """读取期刊内容（去掉 frontmatter）"""
    content = digest_path.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
    if fm_match:
        return content[fm_match.end():]
    return content


def distribute_digest(
    digest_path: Path,
    platforms: list[str],
    dry_run: bool = False,
):
    """将一篇期刊分发到指定平台"""
    digest_content = read_digest_content(digest_path)
    digest_file = str(digest_path.relative_to(PROJECT_ROOT))

    if not digest_content.strip():
        print(f"⚠️  期刊内容为空: {digest_file}")
        return

    state = load_distribute_state()
    file_hash = content_hash(digest_content)

    print(f"\n📤 开始分发: {digest_file}")
    print(f"   内容哈希: {file_hash}")
    print(f"   目标平台: {', '.join(PLATFORM_NAMES.get(p, p) for p in platforms)}")
    print(f"   模式: {'预览（dry-run）' if dry_run else '正式发布'}")
    print()

    results = {}

    for platform in platforms:
        platform_name = PLATFORM_NAMES.get(platform, platform)

        # 检查是否已分发过（相同内容 + 相同平台）
        state_key = f"{digest_file}:{platform}"
        prev = state.get("distributed", {}).get(state_key, {})
        if prev.get("hash") == file_hash and prev.get("success"):
            print(f"  ⏭️  {platform_name}：内容未变化，已分发过，跳过")
            results[platform] = "skipped"
            continue

        print(f"  🤖 正在为 {platform_name} 改编内容...")
        adapted = adapt_content_for_platform(digest_content, platform_name)

        if not adapted:
            print(f"  ⚠️  {platform_name}：AI 改编失败，跳过")
            results[platform] = "adapt_failed"
            continue

        # 预览模式：保存到文件但不发布
        if dry_run:
            DISTRIBUTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            preview_file = DISTRIBUTE_OUTPUT_DIR / f"{platform}_{date_str}_preview.json"
            preview_file.write_text(
                json.dumps(adapted, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  📋 {platform_name}：预览内容已保存到 {preview_file}")
            results[platform] = "preview"
            continue

        # 正式发布
        success = False
        if platform == "xiaohongshu":
            success = publish_to_xiaohongshu(adapted, digest_file)
        elif platform in ALL_PLATFORMS and ALL_PLATFORMS[platform][1]:
            success = ALL_PLATFORMS[platform][1](adapted)
        else:
            print(f"  ⚠️  未知平台: {platform}")
            results[platform] = "unknown"
            continue

        results[platform] = "success" if success else "failed"

        # 记录分发状态
        if success:
            state.setdefault("distributed", {})[state_key] = {
                "hash": file_hash,
                "success": True,
                "time": datetime.now().isoformat(),
                "platform": platform_name,
            }

    # 保存状态
    if not dry_run:
        save_distribute_state(state)

    # 打印汇总
    print(f"\n{'─' * 50}")
    print(f"📊 分发结果汇总:")
    for platform, result in results.items():
        emoji = {
            "success": "✅",
            "skipped": "⏭️",
            "preview": "📋",
            "failed": "❌",
            "adapt_failed": "⚠️",
            "unknown": "❓",
        }.get(result, "❓")
        print(f"   {emoji} {PLATFORM_NAMES.get(platform, platform)}: {result}")


# ─── CLI 入口 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="多平台内容分发 — 将知识期刊分发到社交媒体",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 scripts/distribute.py                          # 分发最新期刊到所有平台
  python3 scripts/distribute.py --type weekly             # 只分发最新周刊
  python3 scripts/distribute.py --file digests/weekly/2025-W01.md  # 分发指定文件
  python3 scripts/distribute.py --platforms weibo,twitter  # 只发到微博和推特
  python3 scripts/distribute.py --dry-run                 # 预览模式
        """,
    )
    parser.add_argument(
        "--type",
        choices=["daily", "weekly", "monthly", "quarterly", "yearly"],
        help="期刊类型（默认自动选择最新的）",
    )
    parser.add_argument(
        "--file",
        help="指定期刊文件路径",
    )
    parser.add_argument(
        "--platforms",
        default="wechat,weibo,twitter,xiaohongshu,zsxq",
        help="目标平台，逗号分隔（默认全部）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，只生成内容不实际发布",
    )

    args = parser.parse_args()

    # 确定要分发的文件
    if args.file:
        digest_path = Path(args.file)
        if not digest_path.is_absolute():
            digest_path = PROJECT_ROOT / digest_path
        if not digest_path.exists():
            print(f"❌ 文件不存在: {args.file}")
            sys.exit(1)
    else:
        digest_path = find_latest_digest(args.type or "")
        if not digest_path:
            print("📭 没有找到可分发的期刊文件")
            sys.exit(0)

    # 解析平台列表
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    valid_platforms = list(ALL_PLATFORMS.keys())
    for p in platforms:
        if p not in valid_platforms:
            print(f"⚠️  未知平台 '{p}'，可选: {', '.join(valid_platforms)}")
            sys.exit(1)

    print("🚀 多平台内容分发")
    print(f"{'═' * 50}")

    distribute_digest(digest_path, platforms, dry_run=args.dry_run)

    print(f"\n🎉 分发流程完成！")


if __name__ == "__main__":
    main()
