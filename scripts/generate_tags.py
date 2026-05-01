#!/usr/bin/env python3
"""
AI 自动标签生成脚本
读取 posts/ 中的文章，调用 DeepSeek AI 为缺少有效标签的文章自动生成标签，
并将标签写回文章的 frontmatter。

使用方式：
    python3 scripts/generate_tags.py              # 为所有缺少标签的文章生成标签
    python3 scripts/generate_tags.py --all         # 为所有文章重新生成标签（覆盖已有标签）
    python3 scripts/generate_tags.py --file posts/xxx.md  # 为指定文章生成标签
    python3 scripts/generate_tags.py --dry-run     # 预览模式，不实际修改文件
"""

from __future__ import annotations

import os
import re
import sys
import json
import argparse
from pathlib import Path
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

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.environ.get(
    "DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"
)
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = PROJECT_ROOT / "posts"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# 默认标签，表示文章还没有被 AI 打过标签
DEFAULT_TAGS = {"notion"}


# ─── AI 调用 ───────────────────────────────────────────────────────

def call_deepseek(prompt: str, system_prompt: str = "") -> str:
    """调用 DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        print("⚠️  DEEPSEEK_API_KEY 未设置，跳过 AI 标签生成")
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
                "temperature": 0.3,
                "max_tokens": 500,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return ""


# ─── 文章解析 ──────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> tuple[dict, str, str]:
    """
    解析文章的 frontmatter 和正文。
    返回 (frontmatter_dict, frontmatter_raw, body)
    """
    fm = {}
    fm_raw = ""
    body = content

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        fm_raw = fm_match.group(1)
        body = content[fm_match.end():]
        for line in fm_raw.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                fm[key.strip()] = val.strip()

    return fm, fm_raw, body


def extract_tags_from_frontmatter(fm: dict) -> list[str]:
    """从 frontmatter 中提取标签列表"""
    tags_str = fm.get("tags", "")
    # 处理 [tag1, tag2] 格式
    tags_str = tags_str.strip("[]")
    if not tags_str:
        return []
    return [t.strip().strip('"').strip("'") for t in tags_str.split(",") if t.strip()]


def has_real_tags(tags: list[str]) -> bool:
    """判断文章是否已有有效标签（不只是默认的 'notion'）"""
    real_tags = [t for t in tags if t.lower() not in DEFAULT_TAGS]
    return len(real_tags) > 0


def collect_existing_tags() -> list[str]:
    """收集所有文章中已有的有效标签（用于保持标签一致性）"""
    all_tags = set()
    for post_path in POSTS_DIR.glob("*.md"):
        if post_path.name == "index.md":
            continue
        try:
            content = post_path.read_text(encoding="utf-8")
            fm, _, _ = parse_frontmatter(content)
            tags = extract_tags_from_frontmatter(fm)
            for t in tags:
                if t.lower() not in DEFAULT_TAGS:
                    all_tags.add(t)
        except Exception:
            continue
    return sorted(all_tags)


# ─── 标签生成 ──────────────────────────────────────────────────────

def load_system_prompt(existing_tags: list[str]) -> str:
    """加载标签生成的系统提示词，并注入已有标签库"""
    prompt_path = PROMPTS_DIR / "tags_system.md"
    if not prompt_path.exists():
        print(f"⚠️  提示词文件不存在: {prompt_path}")
        return ""
    template = prompt_path.read_text(encoding="utf-8").strip()

    if existing_tags:
        tags_str = "、".join(existing_tags)
    else:
        tags_str = "（暂无已有标签，请根据文章内容自由生成）"

    return template.replace("{existing_tags}", tags_str)


def generate_tags_for_post(
    title: str, body: str, system_prompt: str
) -> list[str]:
    """调用 AI 为单篇文章生成标签"""
    # 截取正文前 2000 字，避免 token 过多
    body_truncated = body[:2000]
    user_prompt = f"请为以下文章生成标签：\n\n标题：{title}\n\n正文：\n{body_truncated}"

    raw = call_deepseek(user_prompt, system_prompt)
    if not raw:
        return []

    # 解析 AI 返回的 JSON 标签列表
    try:
        # 清理可能的 markdown 代码块标记
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        tags = json.loads(cleaned)
        if isinstance(tags, list):
            return [str(t).strip() for t in tags if str(t).strip()]
    except json.JSONDecodeError:
        # 尝试从文本中提取标签
        print(f"  ⚠️  AI 返回内容无法解析为 JSON: {raw[:100]}")

    return []


def update_frontmatter_tags(content: str, new_tags: list[str]) -> str:
    """将新标签写入文章的 frontmatter"""
    tags_str = ", ".join(new_tags)

    # 替换已有的 tags 行
    updated = re.sub(
        r"(^---\s*\n.*?)(\ntags:\s*\[.*?\])(.*?\n---\s*\n)",
        rf"\1\ntags: [{tags_str}]\3",
        content,
        count=1,
        flags=re.DOTALL,
    )

    # 如果替换成功（内容有变化），直接返回
    if updated != content:
        return updated

    # 如果没有 tags 行，在 frontmatter 中添加一行
    fm_match = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", content, re.DOTALL)
    if fm_match:
        before = fm_match.group(1)
        fm_body = fm_match.group(2)
        after = fm_match.group(3)
        return f"{before}{fm_body}\ntags: [{tags_str}]{after}{content[fm_match.end():]}"

    return content


# ─── 主流程 ────────────────────────────────────────────────────────

def process_post(
    post_path: Path,
    system_prompt: str,
    force: bool = False,
    dry_run: bool = False,
) -> bool:
    """
    处理单篇文章的标签生成。
    返回 True 表示标签已更新，False 表示跳过。
    """
    content = post_path.read_text(encoding="utf-8")
    fm, fm_raw, body = parse_frontmatter(content)
    title = fm.get("title", post_path.stem).strip('"').strip("'")
    current_tags = extract_tags_from_frontmatter(fm)

    # 判断是否需要生成标签
    if not force and has_real_tags(current_tags):
        print(f"  ⏭️  {post_path.name}：已有标签 {current_tags}，跳过")
        return False

    print(f"  🤖 {post_path.name}：正在生成标签...")
    new_tags = generate_tags_for_post(title, body, system_prompt)

    if not new_tags:
        print(f"  ⚠️  {post_path.name}：标签生成失败")
        return False

    print(f"  🏷️  {post_path.name}：生成标签 {new_tags}")

    if dry_run:
        print(f"  📋 预览模式，不修改文件")
        return True

    # 写回文件
    updated_content = update_frontmatter_tags(content, new_tags)
    post_path.write_text(updated_content, encoding="utf-8")
    print(f"  ✅ {post_path.name}：标签已更新")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="AI 自动标签生成 — 为博客文章智能打标签",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 scripts/generate_tags.py                # 为缺少标签的文章生成标签
  python3 scripts/generate_tags.py --all          # 为所有文章重新生成标签
  python3 scripts/generate_tags.py --file posts/xxx.md  # 为指定文章生成标签
  python3 scripts/generate_tags.py --dry-run      # 预览模式
        """,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="为所有文章重新生成标签（覆盖已有标签）",
    )
    parser.add_argument(
        "--file",
        help="指定文章文件路径",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，只显示生成结果不修改文件",
    )

    args = parser.parse_args()

    print("🏷️  AI 自动标签生成")
    print(f"{'═' * 50}\n")

    # 收集已有标签
    existing_tags = collect_existing_tags()
    if existing_tags:
        print(f"📚 已有标签库: {', '.join(existing_tags)}\n")
    else:
        print("📚 暂无已有标签，将根据文章内容自由生成\n")

    # 加载系统提示词
    system_prompt = load_system_prompt(existing_tags)
    if not system_prompt:
        print("❌ 无法加载提示词，退出")
        sys.exit(1)

    # 确定要处理的文章
    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = PROJECT_ROOT / file_path
        if not file_path.exists():
            print(f"❌ 文件不存在: {args.file}")
            sys.exit(1)
        posts = [file_path]
    else:
        posts = sorted(
            [p for p in POSTS_DIR.glob("*.md") if p.name != "index.md"],
            key=lambda p: p.name,
            reverse=True,
        )

    if not posts:
        print("📭 没有找到文章")
        return

    print(f"📝 共发现 {len(posts)} 篇文章\n")

    updated_count = 0
    skipped_count = 0

    for post_path in posts:
        was_updated = process_post(
            post_path,
            system_prompt,
            force=args.all,
            dry_run=args.dry_run,
        )
        if was_updated:
            updated_count += 1
        else:
            skipped_count += 1

    print(f"\n{'─' * 50}")
    print(f"🎉 标签生成完成！更新 {updated_count} 篇，跳过 {skipped_count} 篇")

    if updated_count > 0 and not args.dry_run:
        print(f"\n💡 提示：标签已写入文章 frontmatter，运行以下命令更新标签页面：")
        print(f"   python3 scripts/generate_sidebar.py")


if __name__ == "__main__":
    main()
