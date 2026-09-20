# 山河入戏 · 文旅 IP 剧本游策划智能体

这是一个用于“AI Agent × 文旅”比赛展示与后续真实开发的前端原型。

## 在线演示

https://hfddth.github.io/sanshuiyouxi/

腾讯云 EdgeOne Makers 部署版本会在同一站点提供网页与 `/chat` Agent 接口，
并使用 Makers 内置的 DeepSeek 兼容模型网关。

## 腾讯云部署

- 静态网页构建到 `dist/`
- Agent 入口：`agents/chat/index.py` → `POST /chat`
- 健康检查：`cloud-functions/health/index.py` → `GET /health`
- 会话请求通过 `Makers-Conversation-Id` 保持同一 Agent 实例
- 知识库直接从 `agent/data/nanxijiang` 的授权 Markdown 文件读取

推送到已关联的 GitHub `main` 分支后，EdgeOne Makers 会自动构建并部署。

## 当前版本 V2

已包含：
- 景区项目输入、地图/资料上传入口
- Agent 自主规划工作台
- 关键 IP 方向选择
- 完整项目档案
- 真实空间剧本地图
- IP / 角色 / 剧情 / 任务 / 线索 / 文化植入
- 游客端 H5 体验预览
- 视觉资产生成任务与 Prompt
- 落地实施架构
- AI 自动审查
- 自然语言局部修改演示
- API Base URL 配置与 `/api/health` 测试

## 本地运行

直接打开 `index.html` 即可；推荐使用 VS Code Live Server 或任意静态服务器。

## 后续后端建议

```text
GitHub
  ↓
Railway / Node.js + Express
  ├── Main Agent
  ├── LLM API
  ├── RAG
  ├── Map Vision
  ├── Image API
  ├── PostgreSQL
  └── Object Storage
```

建议后端提供：
- `GET /api/health`
- `POST /api/projects`
- `POST /api/projects/:id/map`
- `POST /api/projects/:id/generate`
- `POST /api/projects/:id/decision`
- `PATCH /api/projects/:id`
- `GET /api/projects/:id`
- `POST /api/images/generate`

> API Key 不要写入前端文件，也不要提交到 GitHub。

