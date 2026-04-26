#!/usr/bin/env python3
"""
清理失效链接脚本
在构建前运行，扫描 digest 文件中引用的文章链接，
如果对应的 post 文件已不存在，则自动清理。

- 如果 digest 中所有引用的文章都已删除 → 删除该 digest 文件
- 如果 digest 中部分文章已删除 → 从收录列表中移除失效链接
- 清理后自动更新 digest index 页面
"""

import re
from pathlib import Path


POSTS_DIR = Path("posts")
DIGESTS_DIR = Path("digests")

DIGEST_TYPES = [
    ("daily", "日报", "📅"),
    ("weekly", "周刊", "📰"),
    ("monthly", "月刊", "📖"),
    ("quarterly", "季刊", "📚"),
    ("yearly", "年刊", "🏆"),
]


def get_existing_posts() -> set[str]:
    """获取当前存在的所有 post 文件名（不含扩展名）"""
    posts = set()
    for f in POSTS_DIR.glob("*.md"):
        if f.name != "index.md":
            posts.add(f.stem)
    return posts


def extract_post_links(content: str) -> list[str]:
    """从 digest 内容中提取所有 /posts/xxx 链接对应的文件名"""
    # 匹配 ](/posts/xxx) 或 (/posts/xxx) 格式的链接
    return re.findall(r"\(/posts/([^)]+)\)", content)


def remove_dead_links_from_content(content: str, dead_posts: set[str]) -> str:
    """从 digest 内容中移除引用了已删除文章的行"""
    lines = content.split("\n")
    cleaned_lines = []
    removed_count = 0

    for line in lines:
        # 检查这一行是否包含指向已删除文章的链接
        links_in_line = re.findall(r"\(/posts/([^)]+)\)", line)
        if any(link in dead_posts for link in links_in_line):
            removed_count += 1
            continue
        cleaned_lines.append(line)

    if removed_count > 0:
        # 更新收录文章数量
        result = "\n".join(cleaned_lines)
        # 更新 "共收录 X 篇文章" 中的数字
        remaining_posts = extract_post_links(result)
        result = re.sub(
            r"共收录 \d+ 篇文章",
            f"共收录 {len(remaining_posts)} 篇文章",
            result,
        )
        return result

    return content


def cleanup_digest_file(filepath: Path, existing_posts: set[str]) -> bool:
    """
    清理单个 digest 文件。
    返回 True 表示文件被删除，False 表示文件被保留（可能已修改）。
    """
    content = filepath.read_text(encoding="utf-8")
    linked_posts = extract_post_links(content)

    if not linked_posts:
        # 没有文章链接的 digest，保留不动
        return False

    dead_posts = {p for p in linked_posts if p not in existing_posts}

    if not dead_posts:
        # 所有链接都有效，无需处理
        return False

    alive_posts = [p for p in linked_posts if p in existing_posts]

    if not alive_posts:
        # 所有引用的文章都已删除，删除整个 digest 文件
        filepath.unlink()
        print(f"🗑️  删除 {filepath}（所有引用的文章已不存在）")
        return True

    # 部分文章已删除，清理失效链接
    cleaned = remove_dead_links_from_content(content, dead_posts)
    filepath.write_text(cleaned, encoding="utf-8")
    print(f"🧹 清理 {filepath}（移除 {len(dead_posts)} 个失效链接）")
    return False


def update_digest_index(digest_type: str, label: str, emoji: str):
    """更新期刊索引页"""
    digest_dir = DIGESTS_DIR / digest_type
    if not digest_dir.exists():
        return

    files = sorted(
        [f for f in digest_dir.glob("*.md") if f.name != "index.md"],
        reverse=True,
    )

    if files:
        links = "\n".join(
            f"- [{f.stem}](/digests/{digest_type}/{f.stem})"
            for f in files
        )
    else:
        links = "暂无内容。"

    index_content = f"""---
title: {label}
---

# {emoji} {label}

{links}
"""
    (digest_dir / "index.md").write_text(index_content, encoding="utf-8")


def main():
    existing_posts = get_existing_posts()
    print(f"📝 当前共有 {len(existing_posts)} 篇文章\n")

    cleaned_count = 0
    deleted_count = 0

    for digest_type, label, emoji in DIGEST_TYPES:
        digest_dir = DIGESTS_DIR / digest_type
        if not digest_dir.exists():
            continue

        for filepath in sorted(digest_dir.glob("*.md")):
            if filepath.name == "index.md":
                continue
            was_deleted = cleanup_digest_file(filepath, existing_posts)
            if was_deleted:
                deleted_count += 1
            else:
                cleaned_count += 1

    # 更新所有 index 页面
    for digest_type, label, emoji in DIGEST_TYPES:
        update_digest_index(digest_type, label, emoji)

    if deleted_count > 0 or cleaned_count > 0:
        print(f"\n✅ 清理完成：删除 {deleted_count} 个 digest 文件，清理 {cleaned_count} 个文件")
    else:
        print("\n✅ 无需清理，所有链接均有效")


if __name__ == "__main__":
    main()
