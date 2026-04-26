#!/usr/bin/env python3
"""
自动生成 VitePress 侧边栏配置
扫描 posts/ 和 digests/ 目录，生成侧边栏 JSON 供 VitePress 使用。
"""

import json
import re
from pathlib import Path
from datetime import datetime


def parse_date_from_file(filepath: Path) -> str:
    """从文件中提取日期"""
    content = filepath.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if line.strip().startswith("date:"):
                return line.split(":", 1)[1].strip()

    # 从文件名提取
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filepath.stem)
    if date_match:
        return date_match.group(1)
    return ""


def parse_title_from_file(filepath: Path) -> str:
    """从文件中提取标题"""
    content = filepath.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if line.strip().startswith("title:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    return filepath.stem


def generate_posts_sidebar() -> list[dict]:
    """生成博客文章侧边栏"""
    posts_dir = Path("posts")
    posts = []

    for f in posts_dir.glob("*.md"):
        if f.name == "index.md":
            continue
        title = parse_title_from_file(f)
        date = parse_date_from_file(f)
        posts.append({
            "text": f"{date} {title}" if date else title,
            "link": f"/posts/{f.stem}",
            "date": date,
        })

    # 按日期倒序
    posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 去掉 date 字段（VitePress 不需要）
    for p in posts:
        p.pop("date", None)

    return posts


def generate_digest_sidebar(digest_type: str, label: str) -> list[dict]:
    """生成期刊侧边栏"""
    digest_dir = Path("digests") / digest_type
    if not digest_dir.exists():
        return []

    items = []
    for f in sorted(digest_dir.glob("*.md"), reverse=True):
        if f.name == "index.md":
            continue
        items.append({
            "text": f.stem,
            "link": f"/digests/{digest_type}/{f.stem}",
        })

    return items


def main():
    sidebar = {
        "/posts/": [
            {
                "text": "博客文章",
                "items": generate_posts_sidebar(),
            }
        ],
        "/digests/": [
            {
                "text": "日报",
                "collapsed": True,
                "items": generate_digest_sidebar("daily", "日报"),
            },
            {
                "text": "周刊",
                "collapsed": True,
                "items": generate_digest_sidebar("weekly", "周刊"),
            },
            {
                "text": "月刊",
                "collapsed": True,
                "items": generate_digest_sidebar("monthly", "月刊"),
            },
            {
                "text": "季刊",
                "collapsed": True,
                "items": generate_digest_sidebar("quarterly", "季刊"),
            },
            {
                "text": "年刊",
                "collapsed": True,
                "items": generate_digest_sidebar("yearly", "年刊"),
            },
        ],
    }

    output = Path(".vitepress/sidebar.json")
    output.write_text(json.dumps(sidebar, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 侧边栏配置已生成: {output}")


if __name__ == "__main__":
    main()
