#!/usr/bin/env python3
"""
Notion 笔记同步脚本
从 Notion 指定数据库拉取内容，转换为 posts/ 目录下的 markdown 文件。
只同步你指定的那一个数据库，其他 Notion 内容完全不碰。

使用方式：
- 在 Notion 数据库中每天新建一个页面，标题写日期（如 2026-04-26）
- 页面内容写你的思考、链接、笔记
- 脚本会自动拉取新增/修改的页面，生成对应的博客文章

配置方式：
1. 创建 Notion Integration：https://www.notion.so/my-integrations
2. 获取 Integration Token（以 ntn_ 或 secret_ 开头）
3. 在 Notion 中将目标数据库 "Connect to" 你的 Integration
4. 复制数据库 ID（URL 中 notion.so/ 后面那串 32 位字符）
5. 将 Token 和 ID 填入 .env 文件
"""

import os
import re
import json
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

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
NOTION_API_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"

POSTS_DIR = Path("posts")
SYNC_STATE_FILE = Path(".notion_sync_state.json")


# ─── Notion API 调用 ───────────────────────────────────────────────

def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def query_database(
    database_id: str,
    start_cursor: str | None = None,
    last_edited_after: str | None = None,
) -> dict:
    """
    查询 Notion 数据库。
    如果提供 last_edited_after（ISO 时间），只返回在该时间之后编辑过的页面。
    """
    payload: dict = {
        "page_size": 100,
        "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
    }

    if last_edited_after:
        payload["filter"] = {
            "timestamp": "last_edited_time",
            "last_edited_time": {"on_or_after": last_edited_after},
        }

    if start_cursor:
        payload["start_cursor"] = start_cursor

    resp = httpx.post(
        f"{NOTION_API_BASE}/databases/{database_id}/query",
        headers=notion_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_page_blocks(page_id: str, start_cursor: str | None = None) -> dict:
    """获取页面的所有 block 内容"""
    params = {"page_size": 100}
    if start_cursor:
        params["start_cursor"] = start_cursor

    resp = httpx.get(
        f"{NOTION_API_BASE}/blocks/{page_id}/children",
        headers=notion_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_all_page_blocks(page_id: str) -> list[dict]:
    """获取页面的全部 blocks（处理分页）"""
    all_blocks = []
    start_cursor = None

    while True:
        data = get_page_blocks(page_id, start_cursor)
        all_blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return all_blocks


# ─── Notion Block → Markdown 转换 ──────────────────────────────────

def rich_text_to_markdown(rich_texts: list[dict]) -> str:
    """将 Notion rich_text 数组转换为 Markdown 文本"""
    parts = []
    for rt in rich_texts:
        text = rt.get("plain_text", "")
        annotations = rt.get("annotations", {})
        href = rt.get("href")

        # 应用格式
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        if href:
            text = f"[{text}]({href})"

        parts.append(text)

    return "".join(parts)


def block_to_markdown(block: dict, indent: int = 0) -> str:
    """将单个 Notion block 转换为 Markdown"""
    block_type = block.get("type", "")
    prefix = "  " * indent

    if block_type == "paragraph":
        text = rich_text_to_markdown(block["paragraph"].get("rich_text", []))
        return f"{prefix}{text}\n" if text else "\n"

    elif block_type in ("heading_1", "heading_2", "heading_3"):
        level = int(block_type[-1])
        text = rich_text_to_markdown(block[block_type].get("rich_text", []))
        return f"{'#' * level} {text}\n"

    elif block_type == "bulleted_list_item":
        text = rich_text_to_markdown(block["bulleted_list_item"].get("rich_text", []))
        return f"{prefix}- {text}\n"

    elif block_type == "numbered_list_item":
        text = rich_text_to_markdown(block["numbered_list_item"].get("rich_text", []))
        return f"{prefix}1. {text}\n"

    elif block_type == "to_do":
        text = rich_text_to_markdown(block["to_do"].get("rich_text", []))
        checked = "x" if block["to_do"].get("checked") else " "
        return f"{prefix}- [{checked}] {text}\n"

    elif block_type == "toggle":
        text = rich_text_to_markdown(block["toggle"].get("rich_text", []))
        return f"{prefix}<details><summary>{text}</summary>\n\n</details>\n"

    elif block_type == "code":
        text = rich_text_to_markdown(block["code"].get("rich_text", []))
        lang = block["code"].get("language", "")
        return f"```{lang}\n{text}\n```\n"

    elif block_type == "quote":
        text = rich_text_to_markdown(block["quote"].get("rich_text", []))
        lines = text.split("\n")
        return "\n".join(f"> {line}" for line in lines) + "\n"

    elif block_type == "callout":
        icon = block["callout"].get("icon", {})
        emoji = icon.get("emoji", "💡") if icon else "💡"
        text = rich_text_to_markdown(block["callout"].get("rich_text", []))
        return f"> {emoji} {text}\n"

    elif block_type == "divider":
        return "---\n"

    elif block_type == "image":
        image_data = block["image"]
        url = ""
        if image_data.get("type") == "external":
            url = image_data["external"].get("url", "")
        elif image_data.get("type") == "file":
            url = image_data["file"].get("url", "")
        caption = rich_text_to_markdown(image_data.get("caption", []))
        return f"![{caption}]({url})\n"

    elif block_type == "bookmark":
        url = block["bookmark"].get("url", "")
        caption = rich_text_to_markdown(block["bookmark"].get("caption", []))
        return f"[{caption or url}]({url})\n"

    elif block_type == "embed":
        url = block["embed"].get("url", "")
        return f"[嵌入链接]({url})\n"

    elif block_type == "link_preview":
        url = block["link_preview"].get("url", "")
        return f"[链接预览]({url})\n"

    elif block_type == "child_page":
        title = block["child_page"].get("title", "子页面")
        return f"📄 **{title}**\n"

    elif block_type == "child_database":
        title = block["child_database"].get("title", "子数据库")
        return f"📊 **{title}**\n"

    else:
        # 未知类型，尝试提取文本
        type_data = block.get(block_type, {})
        if isinstance(type_data, dict) and "rich_text" in type_data:
            text = rich_text_to_markdown(type_data["rich_text"])
            return f"{prefix}{text}\n" if text else ""
        return ""


def blocks_to_markdown(blocks: list[dict]) -> str:
    """将 blocks 列表转换为完整的 Markdown 文本"""
    lines = []
    for block in blocks:
        md = block_to_markdown(block)
        if md:
            lines.append(md)
    return "\n".join(lines).strip()


# ─── 页面属性提取 ──────────────────────────────────────────────────

def extract_page_title(page: dict) -> str:
    """从 Notion 页面属性中提取标题"""
    properties = page.get("properties", {})

    # 尝试常见的标题属性名
    for key in ("Name", "名称", "Title", "标题", "title", "name"):
        prop = properties.get(key, {})
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)

    # 遍历所有属性找 title 类型
    for key, prop in properties.items():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)

    return "Notion 笔记"


def extract_page_tags(page: dict) -> list[str]:
    """从 Notion 页面属性中提取标签"""
    properties = page.get("properties", {})
    tags = []

    for key in ("Tags", "标签", "tags", "Tag", "Category", "分类"):
        prop = properties.get(key, {})
        if prop.get("type") == "multi_select":
            for option in prop.get("multi_select", []):
                tags.append(option.get("name", ""))
        elif prop.get("type") == "select":
            select = prop.get("select")
            if select:
                tags.append(select.get("name", ""))

    return tags


def extract_date_from_title(title: str) -> str | None:
    """尝试从标题中提取日期（支持 2026-04-26 格式）"""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", title.strip())
    if match:
        return match.group(1)
    return None


def extract_page_date(page: dict) -> str:
    """从 Notion 页面提取日期，优先从标题解析"""
    title = extract_page_title(page)

    # 优先：从标题提取日期（你的用法：标题就是日期）
    title_date = extract_date_from_title(title)
    if title_date:
        return title_date

    # 其次：从 Date 属性提取
    properties = page.get("properties", {})
    for key in ("Date", "日期", "date", "Created", "创建时间"):
        prop = properties.get(key, {})
        if prop.get("type") == "date":
            date_obj = prop.get("date")
            if date_obj and date_obj.get("start"):
                return date_obj["start"][:10]

    # 兜底：使用页面创建时间
    created_time = page.get("created_time", "")
    if created_time:
        return created_time[:10]

    return datetime.now().strftime("%Y-%m-%d")


# ─── 同步状态管理 ──────────────────────────────────────────────────

def load_sync_state() -> dict:
    """加载同步状态"""
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
    return {"synced_pages": {}, "last_sync": None}


def save_sync_state(state: dict):
    """保存同步状态"""
    state["last_sync"] = datetime.now().isoformat()
    SYNC_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── 核心同步逻辑 ──────────────────────────────────────────────────

def fetch_pages(last_edited_after: str | None = None) -> list[dict]:
    """从 Notion 数据库拉取页面（支持增量）"""
    all_pages = []
    start_cursor = None

    while True:
        data = query_database(NOTION_DATABASE_ID, start_cursor, last_edited_after)
        all_pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")
        print(f"  📥 已拉取 {len(all_pages)} 个页面...")

    return all_pages


def page_to_post(page: dict) -> tuple[str, str]:
    """将 Notion 页面转换为 markdown 文件内容，返回 (filename, content)"""
    page_id = page["id"]
    title = extract_page_title(page)
    tags = extract_page_tags(page)
    date_str = extract_page_date(page)

    # 获取页面内容
    print(f"  📖 读取页面内容: {title}")
    blocks = get_all_page_blocks(page_id)
    markdown_body = blocks_to_markdown(blocks)

    # 文件名：直接用日期（你的标题就是日期）
    # 如果标题不是日期格式，加上 notion 前缀避免冲突
    title_date = extract_date_from_title(title)
    if title_date:
        filename = title_date
    else:
        slug = page_id.replace("-", "")[:8]
        filename = f"{date_str}-notion-{slug}"

    # 构建 frontmatter
    tags_str = ", ".join(tags) if tags else "notion"
    content = f"""---
title: "{title}"
date: {date_str}
tags: [{tags_str}]
source: notion
notion_id: {page_id}
---

# {title}

{markdown_body}

## AI 总结

> 此部分由 AI 自动生成

*等待 AI 总结生成...*
"""
    return filename, content


def find_existing_post(notion_id: str) -> Path | None:
    """查找已有的、来自同一个 Notion 页面的博客文件"""
    for post_path in POSTS_DIR.glob("*.md"):
        if post_path.name == "index.md":
            continue
        try:
            content = post_path.read_text(encoding="utf-8")
            if f"notion_id: {notion_id}" in content:
                return post_path
        except Exception:
            continue
    return None


def sync_notion():
    """同步 Notion 数据库内容到 posts/ 目录（增量同步）"""
    if not NOTION_TOKEN:
        print("⚠️  NOTION_TOKEN 未设置，跳过 Notion 同步")
        return

    if not NOTION_DATABASE_ID:
        print("⚠️  NOTION_DATABASE_ID 未设置，跳过 Notion 同步")
        return

    print("🔄 开始同步 Notion 数据库...\n")

    # 加载同步状态
    state = load_sync_state()
    synced_pages = state.get("synced_pages", {})
    last_sync = state.get("last_sync")

    # 增量拉取：只拉取上次同步之后修改过的页面
    if last_sync:
        print(f"   上次同步: {last_sync}")
        print(f"   只拉取此后修改的页面\n")

    try:
        pages = fetch_pages(last_edited_after=last_sync)
    except Exception as e:
        print(f"❌ Notion API 调用失败: {e}")
        return

    if not pages:
        print("📭 没有新增或修改的页面")
        save_sync_state(state)
        return

    print(f"\n📝 获取到 {len(pages)} 个新增/修改的页面")

    # 确保 posts 目录存在
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    new_count = 0
    update_count = 0

    for page in pages:
        page_id = page["id"]
        last_edited = page.get("last_edited_time", "")

        # 跳过已归档的
        if page.get("archived"):
            continue

        # 检查是否已同步且未修改
        prev_edited = synced_pages.get(page_id, {}).get("last_edited")
        if prev_edited and prev_edited == last_edited:
            continue

        try:
            filename, content = page_to_post(page)

            # 检查是否已有对应文件（更新场景）
            existing = find_existing_post(page_id)
            if existing:
                # 保留已有的 AI 总结（如果不是占位符）
                old_content = existing.read_text(encoding="utf-8")
                if "此部分由 AI 自动生成" in old_content and "等待 AI 总结生成" not in old_content:
                    # 提取旧的 AI 总结
                    import re as _re
                    ai_match = _re.search(
                        r"(## AI 总结\s*\n.*)",
                        old_content,
                        _re.DOTALL,
                    )
                    if ai_match:
                        old_ai_section = ai_match.group(1)
                        content = _re.sub(
                            r"## AI 总结\s*\n.*",
                            old_ai_section,
                            content,
                            flags=_re.DOTALL,
                        )

                existing.write_text(content, encoding="utf-8")
                update_count += 1
                print(f"  🔄 更新: {existing.name}")
            else:
                post_path = POSTS_DIR / f"{filename}.md"

                # 避免文件名冲突（和非 Notion 来源的文件）
                if post_path.exists():
                    old_content = post_path.read_text(encoding="utf-8")
                    if f"notion_id:" not in old_content:
                        # 文件存在但不是 Notion 来源，加后缀
                        counter = 1
                        while post_path.exists():
                            post_path = POSTS_DIR / f"{filename}-notion-{counter}.md"
                            counter += 1

                post_path.write_text(content, encoding="utf-8")
                new_count += 1
                print(f"  ✅ 新增: {post_path.name}")

            # 记录同步状态
            synced_pages[page_id] = {
                "last_edited": last_edited,
                "title": extract_page_title(page),
            }

        except Exception as e:
            print(f"  ⚠️  页面同步失败: {e}")
            continue

    # 保存同步状态
    state["synced_pages"] = synced_pages
    save_sync_state(state)

    print(f"\n🎉 Notion 同步完成！新增 {new_count} 篇，更新 {update_count} 篇")


def main():
    sync_notion()


if __name__ == "__main__":
    main()
