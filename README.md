# 🤖 AI Blog

> flomo + Notion 随手记 → AI 自动总结 → 知识期刊 → GitHub Pages

在 flomo 或 Notion 中随手记录每天的思考和链接，**只同步你指定的内容**，AI 自动提取知识点，生成日/周/月/季/年刊，发布到 GitHub Pages。

## ✨ 核心特性

- **双源输入**：同时支持 flomo 和 Notion，哪个顺手用哪个
- **隐私可控**：flomo 只同步带 `#blog-sync` 标签的笔记，Notion 只同步指定数据库，其他内容完全不碰
- **AI 总结**：DeepSeek 自动提取关键知识点，生成结构化摘要
- **自动期刊**：日报、周刊、月刊、季刊、年刊全自动生成
- **零成本部署**：GitHub Pages 免费托管，GitHub Actions 自动化

## 📋 工作流

```
flomo（加 #blog-sync 标签）──┐
                              ├→ GitHub Actions → AI 总结 → 期刊生成 → GitHub Pages
Notion（指定数据库）──────────┘
```

### 日常使用

1. **flomo 随手记**：打开 flomo，写下想法/链接，末尾加 `#blog-sync` → 自动同步
2. **Notion 白板**：打开指定的 Notion 数据库页面，新建条目写内容 → 自动同步
3. **不想同步的**：flomo 不加标签 / Notion 写在其他页面 → 完全不会被同步

## 🚀 快速开始

### 1. Fork 仓库

```bash
git clone https://github.com/liuqinh2s/AI-blog.git
cd AI-blog
npm install
pip install -r requirements.txt
```

### 2. 配置 flomo（可选）

1. 浏览器登录 [flomoapp.com](https://flomoapp.com)
2. F12 → Network → 复制任意请求的 `Authorization` 头中的 Bearer token
3. 填入 `.env` 的 `FLOMO_TOKEN`
4. 写笔记时，想同步的加 `#blog-sync` 标签

### 3. 配置 Notion（可选）

1. 创建 Integration：[notion.so/my-integrations](https://www.notion.so/my-integrations)
2. 在 Notion 中新建一个数据库（比如叫「每日输入白板」）
3. 数据库页面点 `···` → `Connect to` → 选择你的 Integration
4. 复制数据库 ID（URL 中 `notion.so/` 后面那串 32 位字符）
5. 填入 `.env`：
   - `NOTION_TOKEN`：Integration Token
   - `NOTION_DATABASE_ID`：数据库 ID

#### Notion 数据库建议结构

| 属性名 | 类型 | 说明 |
|--------|------|------|
| Name | Title | 标题（必须） |
| Tags | Multi-select | 标签（可选） |
| Date | Date | 日期（可选，不填则用创建时间） |

### 4. 配置 DeepSeek AI

1. 获取 API Key：[platform.deepseek.com](https://platform.deepseek.com/api_keys)
2. 填入 `.env` 的 `DEEPSEEK_API_KEY`

### 5. 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret | 说明 | 必填 |
|--------|------|------|
| `FLOMO_TOKEN` | flomo Bearer token | 使用 flomo 时必填 |
| `NOTION_TOKEN` | Notion Integration Token | 使用 Notion 时必填 |
| `NOTION_DATABASE_ID` | Notion 数据库 ID | 使用 Notion 时必填 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 必填 |

可选的 Variables（Settings → Secrets and variables → Actions → Variables）：

| Variable | 说明 | 默认值 |
|----------|------|--------|
| `FLOMO_SYNC_TAG` | flomo 同步标签名 | `blog-sync` |

### 6. 启用 GitHub Pages

Settings → Pages → Source 选择 `GitHub Actions`

## 🛠️ 本地开发

```bash
# 同步 flomo（仅 #blog-sync 标签）
npm run flomo:sync

# 同步 Notion 数据库
npm run notion:sync

# 同步全部来源
npm run sync:all

# AI 总结
npm run ai:summarize

# 生成期刊
npm run ai:digests

# 生成侧边栏
npm run ai:sidebar

# 一键全流程
npm run ai:all

# 本地预览
npm run dev
```

## 📁 项目结构

```
AI-blog/
├── posts/                    # 博客文章（flomo + Notion 同步过来的）
├── digests/                  # 自动生成的期刊
│   ├── daily/               # 日报
│   ├── weekly/              # 周刊
│   ├── monthly/             # 月刊
│   ├── quarterly/           # 季刊
│   └── yearly/              # 年刊
├── scripts/
│   ├── sync_flomo.py        # flomo 同步（标签过滤）
│   ├── sync_notion.py       # Notion 同步（指定数据库）
│   ├── ai_summarize.py      # AI 总结生成
│   ├── generate_digests.py  # 期刊生成
│   └── generate_sidebar.py  # 侧边栏生成
├── .github/workflows/
│   ├── deploy.yml           # push 触发：同步 + AI + 构建部署
│   └── digests.yml          # 定时触发：每日同步 + 期刊生成
├── .vitepress/              # VitePress 配置
├── .env                     # 本地环境变量（不提交）
└── .env.example             # 环境变量模板
```

## 🔄 自动化流程

- **每次 push**：同步 flomo + Notion → AI 总结 → 构建部署
- **每天 00:00（北京时间）**：同步 flomo + Notion → AI 总结 → 生成期刊 → 构建部署
- **手动触发**：GitHub Actions 页面点 `Run workflow`

## 📝 License

ISC
