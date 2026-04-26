#!/usr/bin/env python3
"""
flomo 笔记同步脚本
从 flomo 拉取带有指定标签的笔记，转换为 posts/ 目录下的 markdown 文件。
默认只同步带 #blog-sync 标签的笔记，其他笔记不会被同步。

使用 flomo 非官方 API（需要 Bearer token）。

token 获取方式：
1. 浏览器登录 https://flomoapp.com
2. 打开开发者工具（F12）→ Network
3. 刷新页面，找到任意 API 请求，复制 Authorization 头中的 Bearer token
"""

import os
import re
import json
import html
from pathlib import Path
from datetime import datetime

import httpx

# 加载 .env 文件
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

FLOMO_TOKEN = os.environ.get("FLOMO_TOKEN", "")
FLOMO_API_BASE = os.environ.get("FLOMO_API_BASE", "https://flomoapp.com/api/v1")
FLOMO_SYNC_TAG = os.environ.get("FLOMO_SYNC_TAG", "blog-sync")
POSTS_DIR = Path("posts")
SYNC_STATE_FILE = Path(".flomo_sync_state.json")


def html_to_markdown(html_content: str) -> str:
    """将 flomo 的 HTML 内容转换为 Markdown"""
    text = html_content

    # 处理段落
    text = re.sub(r"<p>", "", text)
    text = re.sub(r"</p>", "\n", text)

    # 处理换行
    text = re.sub(r"<br\s*/?>", "\n", text)

    # 处理加粗
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text)

    # 处理斜体
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text)

    # 处理链接
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", text)

    # 处理无序列表
    text = re.sub(r"<ul>", "", text)
    text = re.sub(r"</ul>", "", text)
    text = re.sub(r"<li>", "- ", text)
    text = re.sub(r"</li>", "\n", text)

    # 处理有序列表
    text = re.sub(r"<ol>", "", text)
    text = re.sub(r"</ol>", "", text)

    # 处理代码块
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text)

    # 处理删除线
    text = re.sub(r"<del>(.*?)</del>", r"~~\1~~", text)
    text = re.sub(r"<s>(.*?)</s>", r"~~\1~~", text)

    # 处理图片
    text = re.sub(r'<img[^>]*src="([^"]*)"[^>]*/?>',  r"![](\1)", text)

    # 清除剩余 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)

    # HTML 实体解码
    text = html.unescape(text)

    # 清理多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_tags(content: str) -> list[str]:
    """从 flomo 内容中提取 #标签"""
    tags = re.findall(r"#([^\s#]+)", content)
    return tags


def has_sync_tag(memo: dict) -> bool:
    """检查 memo 是否包含同步标签"""
    # 方式1：从 memo 的 tags 字段检查
    memo_tags = memo.get("tags", [])
    if memo_tags:
        for tag in memo_tags:
            tag_name = tag if isinstance(tag, str) else tag.get("name", "")
            if tag_name.strip("#").lower() == FLOMO_SYNC_TAG.lower():
                return True

    # 方式2：从 HTML 内容中检查标签文本
    html_content = memo.get("content", "")
    markdown_text = html_to_markdown(html_content)
    content_tags = extract_tags(markdown_text)
    for tag in content_tags:
        if tag.lower() == FLOMO_SYNC_TAG.lower():
            return True

    return False


def clean_sync_tag(text: str) -> str:
    """从最终内容中移除 #blog-sync 标签（它只是控制标记，不需要展示）"""
    # 移除 #blog-sync 标签，保留其他标签
    text = re.sub(rf"#\s*{re.escape(FLOMO_SYNC_TAG)}\b\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def extract_title(markdown_text: str) -> str:
    """从 markdown 内容中提取标题（取第一行非空文本，截断到合理长度）"""
    for line in markdown_text.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            # 去掉标签
            clean = re.sub(r"#\S+", "", line).strip()
            if clean:
                return clean[:50]
        elif line.startswith("#"):
            clean = line.lstrip("#").strip()
            clean = re.sub(r"#\S+", "", clean).strip()
            if clean:
                return clean[:50]
    return "flomo 笔记"


def load_sync_state() -> dict:
    """加载同步状态（记录已同步的 memo ID）"""
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
    return {"synced_ids": [], "last_sync": None}


def save_sync_state(state: dict):
    """保存同步状态"""
    state["last_sync"] = datetime.now().isoformat()
    SYNC_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_memos(offset: int = 0, limit: int = 200) -> list[dict]:
    """从 flomo API 拉取笔记列表"""
    if not FLOMO_TOKEN:
        print("⚠️  FLOMO_TOKEN 未设置，跳过 flomo 同步")
        return []

    try:
        resp = httpx.get(
            f"{FLOMO_API_BASE}/memo",
            params={"offset": offset, "limit": limit},
            headers={
                "Authorization": f"Bearer {FLOMO_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        print(f"❌ flomo API 调用失败: {e}")
        return []


def fetch_all_memos() -> list[dict]:
    """拉取所有笔记（分页）"""
    all_memos = []
    offset = 0
    limit = 200

    while True:
        memos = fetch_memos(offset=offset, limit=limit)
        if not memos:
            break
        all_memos.extend(memos)
        if len(memos) < limit:
            break
        offset += limit
        print(f"  📥 已拉取 {len(all_memos)} 条笔记...")

    return all_memos


def memo_to_post(memo: dict) -> tuple[str, str]:
    """将 flomo memo 转换为 markdown 文件内容，返回 (filename, content)"""
    # 解析日期
    created_at = memo.get("created_at", "")
    try:
        date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")

    # 转换内容
    html_content = memo.get("content", "")
    markdown_text = html_to_markdown(html_content)

    # 移除 #blog-sync 标签
    markdown_text = clean_sync_tag(markdown_text)

    # 提取标签（排除 blog-sync）和标题
    tags = [t for t in extract_tags(markdown_text) if t.lower() != FLOMO_SYNC_TAG.lower()]
    title = extract_title(markdown_text)

    # 生成文件名：日期-memo_slug
    slug = memo.get("slug", "")[:8] or str(memo.get("id", "unknown"))
    filename = f"{date_str}-{slug}"

    # 构建 frontmatter
    tags_str = ", ".join(tags) if tags else "flomo"
    content = f"""---
title: "{title}"
date: {date_str}
tags: [{tags_str}]
source: flomo
flomo_slug: {memo.get("slug", "")}
---

# {title}

## 原文/素材

{markdown_text}

## 我的思考



## AI 总结

> 此部分由 AI 自动生成

*等待 AI 总结生成...*
"""
    return filename, content


def sync_memos():
    """同步 flomo 笔记到 posts/ 目录（只同步带 #blog-sync 标签的）"""
    print(f"🔄 开始同步 flomo 笔记（仅同步带 #{FLOMO_SYNC_TAG} 标签的笔记）...\n")

    # 加载同步状态
    state = load_sync_state()
    synced_ids = set(state.get("synced_ids", []))

    # 拉取所有笔记
    memos = fetch_all_memos()
    if not memos:
        print("📭 没有获取到 flomo 笔记")
        return

    print(f"\n📝 共获取 {len(memos)} 条 flomo 笔记")

    # 过滤：只保留带 #blog-sync 标签的笔记
    sync_memos_list = [m for m in memos if has_sync_tag(m)]
    print(f"🏷️  其中带 #{FLOMO_SYNC_TAG} 标签的有 {len(sync_memos_list)} 条")

    # 确保 posts 目录存在
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    new_count = 0
    for memo in sync_memos_list:
        memo_slug = memo.get("slug", "")
        memo_id = memo_slug or str(memo.get("id", ""))

        # 跳过已同步的
        if memo_id in synced_ids:
            continue

        # 跳过被删除的
        if memo.get("deleted_at"):
            continue

        filename, content = memo_to_post(memo)
        post_path = POSTS_DIR / f"{filename}.md"

        # 避免文件名冲突
        counter = 1
        while post_path.exists():
            post_path = POSTS_DIR / f"{filename}-{counter}.md"
            counter += 1

        post_path.write_text(content, encoding="utf-8")
        synced_ids.add(memo_id)
        new_count += 1
        print(f"  ✅ 同步: {post_path.name}")

    # 保存同步状态
    state["synced_ids"] = list(synced_ids)
    save_sync_state(state)

    print(f"\n🎉 flomo 同步完成！新增 {new_count} 篇文章")


def main():
    sync_memos()


if __name__ == "__main__":
    main()
