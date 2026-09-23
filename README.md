# 山水有戏 · 文旅 IP 剧本游策划智能体

[![Agent CI](https://github.com/hfddth/sanshuiyouxi/actions/workflows/agent-ci.yml/badge.svg)](https://github.com/hfddth/sanshuiyouxi/actions/workflows/agent-ci.yml)

这是“山水有戏”的网页与 Railway Agent 源码。仓库只保留线上运行所需的静态网页、FastAPI Agent、知识库和容器配置。

## 在线地址

- 网页：https://hfddth.github.io/sanshuiyouxi/
- Agent：https://api.hfddth.cn
- 健康检查：https://api.hfddth.cn/health

网页从 `agent-config.js` 读取 Agent 地址，直接请求 Railway 的 `/chat` 接口；API 密钥只配置在 Railway 环境变量中，不进入网页或 GitHub。

## Railway 部署

Railway 服务使用：

- Root Directory：`/agent`
- Dockerfile：`/agent/Dockerfile`
- 健康检查：`/health`
- 运行端口：Railway 注入的 `PORT`
- 必需密钥变量：`DEEPSEEK_API_KEY`

`/health` 会同时检查模型密钥和知识库；任一缺失时返回 HTTP 503，防止 Railway 把不可用实例标记为健康。

可选配置变量：

- `LLM_PROVIDER`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `ALLOWED_ORIGINS`

推送到 `main` 后，由已连接的 Railway 服务自动构建和部署。
GitHub Actions 会先编译 Python、运行接口与知识库测试、检查网页 JavaScript，并构建与 Railway 相同的 Docker 镜像。

## 仓库结构

```text
agent/                 Railway Agent
  data/nanxijiang/     授权知识库
  Dockerfile           容器构建入口
  main.py              FastAPI 入口
agent-config.js        网页使用的 Railway 地址
app.js                 网页逻辑
index.html             网页入口
styles.css             网页样式
sample-script.json     网页示例
```

## 安全

- 不要把 `.env` 或真实 API 密钥提交到 GitHub。
- `.env.example` 只列变量名与示例，不保存真实密钥。
- 前端不保存、传输或展示模型 API 密钥。
