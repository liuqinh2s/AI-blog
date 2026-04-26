#!/usr/bin/env python3
"""
期刊自动生成脚本
根据 posts/ 中的文章，自动生成日报、周刊、月刊、季刊、年刊。
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

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

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

POSTS_DIR = Path("posts")
DIGESTS_DIR = Path("digests")


def call_deepseek(prompt: str, system_prompt: str = "") -> str:
    """调用 DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        print("⚠️  DEEPSEEK_API_KEY 未设置，跳过 AI 生成")
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
                "max_tokens": 4000,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return ""


def parse_post(post_path: Path) -> dict:
    """解析文章，提取 frontmatter 和内容"""
    content = post_path.read_text(encoding="utf-8")

    # 解析 frontmatter
    fm = {}
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                fm[key.strip()] = val.strip()
        body = content[fm_match.end():]
    else:
        body = content

    # 提取日期
    date_str = fm.get("date", "")
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        # 尝试从文件名提取日期
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", post_path.stem)
        if date_match:
            date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
        else:
            date = datetime.fromtimestamp(post_path.stat().st_mtime)

    return {
        "path": post_path,
        "title": fm.get("title", post_path.stem),
        "date": date,
        "tags": fm.get("tags", ""),
        "body": body,
        "filename": post_path.stem,
    }


def get_all_posts() -> list[dict]:
    """获取所有文章并按日期排序"""
    posts = []
    for p in POSTS_DIR.glob("*.md"):
        if p.name == "index.md":
            continue
        posts.append(parse_post(p))
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


def group_posts_by_date(posts: list[dict]) -> dict[str, list[dict]]:
    """按日期分组"""
    groups = defaultdict(list)
    for p in posts:
        groups[p["date"].strftime("%Y-%m-%d")].append(p)
    return dict(groups)


def group_posts_by_week(posts: list[dict]) -> dict[str, list[dict]]:
    """按周分组（ISO 周）"""
    groups = defaultdict(list)
    for p in posts:
        year, week, _ = p["date"].isocalendar()
        key = f"{year}-W{week:02d}"
        groups[key].append(p)
    return dict(groups)


def group_posts_by_month(posts: list[dict]) -> dict[str, list[dict]]:
    """按月分组"""
    groups = defaultdict(list)
    for p in posts:
        groups[p["date"].strftime("%Y-%m")].append(p)
    return dict(groups)


def group_posts_by_quarter(posts: list[dict]) -> dict[str, list[dict]]:
    """按季度分组"""
    groups = defaultdict(list)
    for p in posts:
        quarter = (p["date"].month - 1) // 3 + 1
        key = f"{p['date'].year}-Q{quarter}"
        groups[key].append(p)
    return dict(groups)


def group_posts_by_year(posts: list[dict]) -> dict[str, list[dict]]:
    """按年分组"""
    groups = defaultdict(list)
    for p in posts:
        groups[str(p["date"].year)].append(p)
    return dict(groups)


def posts_to_summary_text(posts: list[dict]) -> str:
    """将一组文章转为供 AI 总结的文本"""
    parts = []
    for p in posts:
        # 提取 AI 总结之前的内容
        body = re.split(r"##\s*AI\s*总结", p["body"], maxsplit=1)[0].strip()
        parts.append(f"### {p['title']} ({p['date'].strftime('%Y-%m-%d')})\n{body[:2000]}")
    return "\n\n---\n\n".join(parts)


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    """从 prompts/ 目录加载提示词文件"""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        print(f"⚠️  提示词文件不存在: {prompt_path}")
        return ""
    return prompt_path.read_text(encoding="utf-8").strip()


DIGEST_SYSTEM_PROMPT = load_prompt("digest_system.md")


def generate_digest_content(
    period_name: str, period_key: str, posts: list[dict]
) -> str:
    """生成期刊内容"""
    summary_text = posts_to_summary_text(posts)

    if not summary_text.strip():
        return ""

    ai_content = call_deepseek(
        f"请为以下「{period_name}」的笔记生成知识期刊：\n\n{summary_text}",
        DIGEST_SYSTEM_PROMPT,
    )

    # 构建文章列表
    post_list = "\n".join(
        f"- [{p['title']}](/posts/{p['filename']}) ({p['date'].strftime('%Y-%m-%d')})"
        for p in posts
    )

    content = f"""---
title: "{period_name}"
date: {datetime.now().strftime('%Y-%m-%d')}
---

# {period_name}

> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}，共收录 {len(posts)} 篇文章

## 收录文章

{post_list}

## AI 知识期刊

{ai_content if ai_content else '*AI 总结生成中...*'}
"""
    return content


def is_period_ended_daily(date_str: str) -> bool:
    """判断某天是否已经过去（包含当天，当天的日报当天即可生成）"""
    today = datetime.now().strftime("%Y-%m-%d")
    return date_str <= today


def is_period_ended_weekly(week_str: str) -> bool:
    """判断某周是否已经结束（只生成上周及更早的周刊）"""
    year, week = week_str.split("-W")
    # ISO 周的最后一天是周日，下周一才生成
    from datetime import date
    last_day = date.fromisocalendar(int(year), int(week), 7)  # 周日
    return date.today() > last_day


def is_period_ended_monthly(month_str: str) -> bool:
    """判断某月是否已经结束"""
    year, month = month_str.split("-")
    if int(month) == 12:
        next_month_first = datetime(int(year) + 1, 1, 1)
    else:
        next_month_first = datetime(int(year), int(month) + 1, 1)
    return datetime.now() >= next_month_first


def is_period_ended_quarterly(quarter_str: str) -> bool:
    """判断某季度是否已经结束"""
    year, q = quarter_str.split("-Q")
    quarter_end_month = int(q) * 3
    if quarter_end_month == 12:
        next_period = datetime(int(year) + 1, 1, 1)
    else:
        next_period = datetime(int(year), quarter_end_month + 1, 1)
    return datetime.now() >= next_period


def is_period_ended_yearly(year_str: str) -> bool:
    """判断某年是否已经结束"""
    return datetime.now() >= datetime(int(year_str) + 1, 1, 1)


def generate_daily_digests(posts: list[dict]):
    """生成日报（只生成昨天及更早的）"""
    daily_dir = DIGESTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    groups = group_posts_by_date(posts)
    for date_str, day_posts in groups.items():
        output = daily_dir / f"{date_str}.md"
        if output.exists():
            print(f"⏭️  日报 {date_str} 已存在，跳过")
            continue
        if not is_period_ended_daily(date_str):
            print(f"⏭️  日报 {date_str}: 日期在未来，跳过")
            continue
        print(f"📅 生成日报: {date_str}")
        content = generate_digest_content(f"{date_str} 日报", date_str, day_posts)
        if content:
            output.write_text(content, encoding="utf-8")
            print(f"✅ 日报 {date_str} 已生成")


def generate_weekly_digests(posts: list[dict]):
    """生成周刊（只生成已结束的周）"""
    weekly_dir = DIGESTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    groups = group_posts_by_week(posts)
    for week_str, week_posts in groups.items():
        output = weekly_dir / f"{week_str}.md"
        if output.exists():
            print(f"⏭️  周刊 {week_str} 已存在，跳过")
            continue
        if not is_period_ended_weekly(week_str):
            print(f"⏭️  周刊 {week_str}: 本周还未结束，跳过")
            continue
        print(f"📰 生成周刊: {week_str}")
        content = generate_digest_content(f"{week_str} 周刊", week_str, week_posts)
        if content:
            output.write_text(content, encoding="utf-8")
            print(f"✅ 周刊 {week_str} 已生成")


def generate_monthly_digests(posts: list[dict]):
    """生成月刊（只生成已结束的月）"""
    monthly_dir = DIGESTS_DIR / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    groups = group_posts_by_month(posts)
    for month_str, month_posts in groups.items():
        output = monthly_dir / f"{month_str}.md"
        if output.exists():
            print(f"⏭️  月刊 {month_str} 已存在，跳过")
            continue
        if not is_period_ended_monthly(month_str):
            print(f"⏭️  月刊 {month_str}: 本月还未结束，跳过")
            continue
        print(f"📖 生成月刊: {month_str}")
        content = generate_digest_content(f"{month_str} 月刊", month_str, month_posts)
        if content:
            output.write_text(content, encoding="utf-8")
            print(f"✅ 月刊 {month_str} 已生成")


def generate_quarterly_digests(posts: list[dict]):
    """生成季刊（只生成已结束的季度）"""
    quarterly_dir = DIGESTS_DIR / "quarterly"
    quarterly_dir.mkdir(parents=True, exist_ok=True)

    groups = group_posts_by_quarter(posts)
    for quarter_str, quarter_posts in groups.items():
        output = quarterly_dir / f"{quarter_str}.md"
        if output.exists():
            print(f"⏭️  季刊 {quarter_str} 已存在，跳过")
            continue
        if not is_period_ended_quarterly(quarter_str):
            print(f"⏭️  季刊 {quarter_str}: 本季度还未结束，跳过")
            continue
        print(f"📚 生成季刊: {quarter_str}")
        content = generate_digest_content(f"{quarter_str} 季刊", quarter_str, quarter_posts)
        if content:
            output.write_text(content, encoding="utf-8")
            print(f"✅ 季刊 {quarter_str} 已生成")


def generate_yearly_digests(posts: list[dict]):
    """生成年刊（只生成已结束的年）"""
    yearly_dir = DIGESTS_DIR / "yearly"
    yearly_dir.mkdir(parents=True, exist_ok=True)

    groups = group_posts_by_year(posts)
    for year_str, year_posts in groups.items():
        output = yearly_dir / f"{year_str}.md"
        if output.exists():
            print(f"⏭️  年刊 {year_str} 已存在，跳过")
            continue
        if not is_period_ended_yearly(year_str):
            print(f"⏭️  年刊 {year_str}: 本年还未结束，跳过")
            continue
        print(f"🏆 生成年刊: {year_str}")
        content = generate_digest_content(f"{year_str} 年度学习报告", year_str, year_posts)
        if content:
            output.write_text(content, encoding="utf-8")
            print(f"✅ 年刊 {year_str} 已生成")


def update_digest_index(digest_type: str, label: str, emoji: str):
    """更新期刊索引页"""
    digest_dir = DIGESTS_DIR / digest_type
    if not digest_dir.exists():
        return

    files = sorted(
        [f for f in digest_dir.glob("*.md") if f.name != "index.md"],
        reverse=True,
    )

    if not files:
        return

    links = "\n".join(
        f"- [{f.stem}](/digests/{digest_type}/{f.stem})"
        for f in files
    )

    index_content = f"""---
title: {label}
---

# {emoji} {label}

{links}
"""
    (digest_dir / "index.md").write_text(index_content, encoding="utf-8")
    print(f"📋 更新了 {label} 索引页")


def main():
    posts = get_all_posts()
    if not posts:
        print("📭 没有文章，跳过期刊生成")
        return

    print(f"📝 共发现 {len(posts)} 篇文章\n")

    generate_daily_digests(posts)
    generate_weekly_digests(posts)
    generate_monthly_digests(posts)
    generate_quarterly_digests(posts)
    generate_yearly_digests(posts)

    # 更新索引页
    update_digest_index("daily", "日报", "📅")
    update_digest_index("weekly", "周刊", "📰")
    update_digest_index("monthly", "月刊", "📖")
    update_digest_index("quarterly", "季刊", "📚")
    update_digest_index("yearly", "年刊", "🏆")

    print("\n🎉 期刊生成完成！")


if __name__ == "__main__":
    main()
