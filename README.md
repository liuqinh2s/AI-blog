# AI Blog

随手记 + AI 总结，自动生成知识期刊。

## 工作原理

```
Obsidian 写笔记 → obsidian-git push → GitHub Actions 自动触发：
  ① AI 读取新文章，生成知识点总结（DeepSeek V4 Flash）
  ② 自动生成/更新 日报、周刊、月刊、季刊、年刊
  ③ VitePress 构建静态网站
  ④ 部署到 GitHub Pages
```

## 项目结构

```
├── posts/                    # 博客文章（Obsidian 写作目录）
│   └── 2025-01-01-hello.md   # 文章格式：日期-标题.md
├── digests/                  # AI 自动生成的期刊
│   ├── daily/                # 日报
│   ├── weekly/               # 周刊
│   ├── monthly/              # 月刊
│   ├── quarterly/            # 季刊
│   └── yearly/               # 年刊
├── scripts/
│   ├── ai_summarize.py       # AI 文章总结脚本
│   ├── generate_digests.py   # 期刊生成脚本
│   └── generate_sidebar.py   # 侧边栏自动生成
├── .vitepress/
│   └── config.mts            # VitePress 配置
├── .github/workflows/
│   └── deploy.yml            # GitHub Actions（push 触发）
└── index.md                  # 首页
```

## 写作格式

在 `posts/` 目录下创建 markdown 文件，命名格式 `YYYY-MM-DD-标题.md`：

```markdown
---
title: 文章标题
date: 2025-01-01
tags: [标签1, 标签2]
---

# 文章标题

## 原文/素材

（粘贴你看到的文章或资料）

## 我的思考

（写你的想法）

## AI 总结

> 此部分由 AI 自动生成

*等待 AI 总结生成...*
```

push 后 AI 会自动替换 "AI 总结" 部分。

## 本地开发

```bash
# 安装依赖
npm install
pip3 install -r requirements.txt

# 本地预览
npm run dev

# 手动运行 AI 总结（需要设置 DEEPSEEK_API_KEY 环境变量）
export DEEPSEEK_API_KEY=你的key
npm run ai:all
```

## GitHub 配置

1. 仓库 Settings → Pages → Source 选择 **GitHub Actions**
2. 仓库 Settings → Secrets → Actions 添加 `DEEPSEEK_API_KEY`

## 技术栈

- **VitePress** - 静态网站生成
- **DeepSeek V4 Flash** - AI 总结
- **GitHub Actions** - 自动化构建部署
- **GitHub Pages** - 静态托管
- **Obsidian** - 本地写作
