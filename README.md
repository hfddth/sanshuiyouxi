# 山河入戏 · 文旅 IP 剧本游策划智能体

这是一个用于“AI Agent × 文旅”比赛展示与后续真实开发的前端原型。

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

