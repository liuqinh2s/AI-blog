#!/usr/bin/env python3
"""
AI 博客总结脚本
读取 posts/ 目录下新增或修改的 markdown 文件，调用 DeepSeek AI 生成总结，
回写到文章的 "## AI 总结" 部分。
"""

import os
import re
import sys
import json
import glob
import subprocess
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

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

POSTS_DIR = Path("posts")


def call_deepseek(prompt: str, system_prompt: str = "") -> str:
    """调用 DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        print("⚠️  DEEPSEEK_API_KEY 未设置，跳过 AI 总结")
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
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return ""


def get_changed_posts() -> list[Path]:
    """获取本次 push 中变更的 posts 文件"""
    # 尝试从 git diff 获取变更文件
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, check=True
        )
        changed = [
            Path(f) for f in result.stdout.strip().split("\n")
            if f.startswith("posts/") and f.endswith(".md") and f != "posts/index.md"
        ]
        if changed:
            return changed
    except Exception:
        pass

    # fallback: 处理所有 posts
    return [
        p for p in POSTS_DIR.glob("*.md")
        if p.name != "index.md"
    ]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 frontmatter 和正文"""
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = content[fm_match.end():]
        # 简单解析 YAML frontmatter
        fm = {}
        for line in fm_text.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                fm[key.strip()] = val.strip().strip("[]").strip()
        return fm, body
    return {}, content


def extract_content_for_ai(body: str) -> str:
    """提取需要 AI 总结的内容（AI 总结部分之前的内容）"""
    # 去掉已有的 AI 总结部分
    ai_section = re.split(r"##\s*AI\s*总结", body, maxsplit=1)
    return ai_section[0].strip()


def inject_ai_summary(content: str, summary: str) -> str:
    """将 AI 总结注入到文章中"""
    # 替换已有的 AI 总结部分
    pattern = r"(##\s*AI\s*总结\s*\n).*"
    replacement = f"## AI 总结\n\n> 此部分由 AI 自动生成（{datetime.now().strftime('%Y-%m-%d')}）\n\n{summary}"

    if re.search(pattern, content, re.DOTALL):
        return re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        # 没有 AI 总结部分，追加到末尾
        return content.rstrip() + f"\n\n{replacement}\n"


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    """从 prompts/ 目录加载提示词文件"""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        print(f"⚠️  提示词文件不存在: {prompt_path}")
        return ""
    return prompt_path.read_text(encoding="utf-8").strip()


SYSTEM_PROMPT = load_prompt("summarize_system.md")


def summarize_post(post_path: Path) -> bool:
    """对单篇文章生成 AI 总结"""
    content = post_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    article_content = extract_content_for_ai(body)

    if not article_content or len(article_content) < 20:
        print(f"⏭️  {post_path.name}: 内容太短，跳过")
        return False

    # 检查是否已有非占位符的 AI 总结
    if "此部分由 AI 自动生成" in content and "等待 AI 总结生成" not in content:
        print(f"⏭️  {post_path.name}: 已有 AI 总结，跳过")
        return False

    print(f"🤖 正在为 {post_path.name} 生成 AI 总结...")
    summary = call_deepseek(
        f"请为以下笔记提取关键知识点并总结：\n\n{article_content}",
        SYSTEM_PROMPT
    )

    if not summary:
        print(f"⚠️  {post_path.name}: AI 总结生成失败")
        return False

    new_content = inject_ai_summary(content, summary)
    post_path.write_text(new_content, encoding="utf-8")
    print(f"✅ {post_path.name}: AI 总结已生成")
    return True


def main():
    changed_posts = get_changed_posts()
    if not changed_posts:
        print("📭 没有需要处理的文章")
        return

    print(f"📝 发现 {len(changed_posts)} 篇文章需要处理")
    success_count = 0
    for post in changed_posts:
        if post.exists():
            if summarize_post(post):
                success_count += 1

    print(f"\n🎉 完成！成功处理 {success_count} 篇文章")


if __name__ == "__main__":
    main()
