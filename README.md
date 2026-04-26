# 🤖 AI Blog

> Notion 随手记 → AI 自动总结 → 知识期刊 → GitHub Pages

在 Notion 中随手记录每天的思考和链接，**只同步你指定的数据库**，AI 自动提取知识点，生成日/周/月/季/年刊，发布到 GitHub Pages。

## ✨ 核心特性

- **Notion 输入**：在 Notion 指定数据库中随手记录，自动同步到博客
- **隐私可控**：只同步指定数据库，其他 Notion 内容完全不碰
- **AI 期刊**：DeepSeek 自动生成日报、周刊、月刊、季刊、年刊
- **多平台分发**：AI 改编内容，自动分发到微信公众号、微博、推特、小红书、知识星球
- **零成本部署**：GitHub Pages 免费托管，GitHub Actions 自动化

## 📋 工作流

```
Notion（指定数据库）→ GitHub Actions → 期刊生成 → 多平台分发 → GitHub Pages
```

### 日常使用

1. **Notion 记录**：打开指定的 Notion 数据库页面，新建条目写内容 → 自动同步
2. **不想同步的**：写在其他 Notion 页面 → 完全不会被同步

## 🚀 快速开始

### 1. Fork 仓库

```bash
git clone https://github.com/liuqinh2s/AI-blog.git
cd AI-blog
npm install
pip install -r requirements.txt
```

### 2. 配置 Notion

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

### 3. 配置 DeepSeek AI

1. 获取 API Key：[platform.deepseek.com](https://platform.deepseek.com/api_keys)
2. 填入 `.env` 的 `DEEPSEEK_API_KEY`

### 4. 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret | 说明 | 必填 |
|--------|------|------|
| `NOTION_TOKEN` | Notion Integration Token | 必填 |
| `NOTION_DATABASE_ID` | Notion 数据库 ID | 必填 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 必填 |

多平台分发相关 Secrets（选填，配置哪个平台就分发到哪个平台）：

| Secret | 说明 |
|--------|------|
| `WECHAT_APPID` | 微信公众号 AppID |
| `WECHAT_SECRET` | 微信公众号 AppSecret |
| `WEIBO_ACCESS_TOKEN` | 微博 access_token |
| `TWITTER_API_KEY` | 推特 API Key |
| `TWITTER_API_SECRET` | 推特 API Secret |
| `TWITTER_ACCESS_TOKEN` | 推特 Access Token |
| `TWITTER_ACCESS_SECRET` | 推特 Access Secret |
| `ZSXQ_ACCESS_TOKEN` | 知识星球 access_token |
| `ZSXQ_GROUP_ID` | 知识星球 group_id |

### 5. 启用 GitHub Pages

Settings → Pages → Source 选择 `GitHub Actions`

## 🛠️ 本地开发

```bash
# 同步 Notion 数据库
npm run notion:sync

# 同步全部来源
npm run sync:all

# 生成期刊
npm run ai:digests

# 生成侧边栏
npm run ai:sidebar

# 多平台分发
npm run ai:distribute

# 预览分发内容（不实际发布）
npm run ai:distribute:preview

# 一键全流程
npm run ai:all

# 本地预览
npm run dev
```

## 📁 项目结构

```
AI-blog/
├── posts/                    # 博客文章（Notion 同步过来的）
├── digests/                  # 自动生成的期刊
│   ├── daily/               # 日报
│   ├── weekly/              # 周刊
│   ├── monthly/             # 月刊
│   ├── quarterly/           # 季刊
│   └── yearly/              # 年刊
├── scripts/
│   ├── sync_notion.py       # Notion 同步（指定数据库）
│   ├── generate_digests.py  # 期刊生成
│   ├── generate_sidebar.py  # 侧边栏生成
│   ├── cleanup_dead_links.py # 失效链接清理
│   └── distribute.py        # 多平台内容分发
├── prompts/
│   ├── digest_system.md     # 期刊生成提示词
│   └── distribute_system.md # 内容分发提示词
├── .github/workflows/
│   ├── deploy.yml           # push 触发：同步 + 构建部署
│   ├── digests.yml          # 定时触发：每日同步 + 期刊生成
│   └── distribute.yml       # 期刊生成后自动分发到社交平台
├── .vitepress/              # VitePress 配置
├── .env                     # 本地环境变量（不提交）
└── .env.example             # 环境变量模板
```

## 🔄 自动化流程

- **每次 push**：同步 Notion → 构建部署
- **每天 00:00（北京时间）**：同步 Notion → 生成期刊 → 多平台分发 → 构建部署
- **手动触发**：GitHub Actions 页面点 `Run workflow`

## 📝 License

ISC
