# Tabbit2API v2.1

[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)

**Tabbit2API** 将 Tabbit 浏览器网页端内部 API 转换为 **OpenAI Chat Completions** 和 **Anthropic Claude Messages** 兼容的标准化接口，让 WorkBuddy、Trae、CodeBuddy、Cherry Studio 等 AI Agent 无缝使用 Tabbit 的模型能力。

> 架构类型：Web 端反代方案（类 Pandora / ChatGPT-Next-Web）  
> 支持域名：`web.tabbit.com`（国内版）/ `web.tabbit.ai`（国际版）

## ✨ 特性

- **双协议兼容** — OpenAI `/v1/chat/completions` + Claude `/v1/messages`
- **Premium 模型支持** — Kimi-K3 通过 v3 API 自动分流
- **Agent 级消息清洗** — 自动过滤伪请求（标题生成等），去重 system/tool 消息，从超长消息中精准提取 `<user_query>` 真实问题
- **上下文管理** — 滑动窗口 + Token 估算，防止上下文溢出
- **Token 池增强** — 加权轮询 + ACTIVE/COOLDOWN/BANNED 状态机 + Fernet 加密存储
- **Agent 模型路由** — 支持 `X-Agent-Phase` 头部按阶段选择不同模型
- **Tool Calling 支持** — 解析 OpenAI tools 定义，注入工具 prompt，检测工具调用输出
- **对话记忆** — Session 自动缓存，同一 API Key 共享 Tabbit room，保持上下文连续
- **永久会话** — 默认 TTL 7 天，用户可在管理面板管理所有活跃会话
- **固定绑定** — 可手动绑定 Tabbit room，实现真正的永久对话
- **并发锁** — asyncio 锁防止 409 冲突，请求排队
- **429 自动重试** — 触发限流后等待重试
- **管理面板** — 模型管理、会话管理、Agent 状态监控、Settings 功能开关
- **配置预览** — 根据访问来源自动判断 localhost 或公网 IP，展示 OpenAI / Claude 完整配置
- **Docker 一键部署**

## 🚀 快速开始

```bash
cd /path/to/tabbit2api
docker compose up -d
```

服务默认监听 `http://localhost:8800`。

### 端口说明

| 地址 | 说明 |
|------|------|
| `http://localhost:8800/v1/chat/completions` | OpenAI 兼容端点 |
| `http://localhost:8800/v1/messages` | Claude 兼容端点 |
| `http://localhost:8800/v1/models` | 模型列表 |
| `http://localhost:8800/admin` | 管理面板（默认密码 `admin`） |
| `http://localhost:8800/health` | 健康检查 |

### 添加 Tabbit Token

首次使用需为每个 Tabbit 账号添加一个 **Access Token**（管理面板 → Tokens 管理 → 添加 Token）。
获取方法见 **[TOKEN.md](./TOKEN.md)**（也可用 `tools/get_tabbit_token.mjs` 一键导出）。

## 📦 模型列表（20 个）

| 模型 ID | 名称 | 类型 | 说明 |
|---------|------|------|------|
| `best` | 最佳 | 免费 | 默认模式，不消耗用量 |
| `kimi-k3` | Kimi-K3 | **PRO** | Kimi 最强旗舰，1M 上下文 |
| `longcat-2-0` | LongCat-2.0 | 免费 | 美团最新旗舰，1M 上下文 |
| `glm-5-2` | GLM-5.2 | 免费 | 智谱最新文本模型 |
| `qwen3-7-max` | Qwen3.7-Max | 免费 | 阿里千问旗舰文本 |
| `kimi-k2-7-code` | Kimi-K2.7-Code | 免费 | 旗舰多模态 Coding |
| `deepseek-v4-pro` | DeepSeek-V4-Pro | 免费 | DeepSeek 旗舰 Pro |
| `deepseek-v4-flash` | DeepSeek-V4-Flash | 免费 | DeepSeek 旗舰 Flash |
| `doubao-seed-2-1-pro` | Doubao-Seed-2.1-Pro | 免费 | 字节旗舰多模态 Pro |
| `doubao-seed-2-1-turbo` | Doubao-Seed-2.1-Turbo | 免费 | 字节旗舰多模态 Turbo |
| `minimax-m3` | MiniMax-M3 | 免费 | MiniMax 原生多模态 |
| `glm-5-1` | GLM-5.1 | 免费 | 智谱文本模型 |
| `glm-5v-turbo` | GLM-5V-Turbo | 免费 | 智谱多模态 |
| `kimi-k2-6` | Kimi-K2.6 | 免费 | Moonshot 旗舰多模态 |
| `kimi-k2-5` | Kimi-K2.5 | 免费 | Moonshot 旗舰多模态 |
| `minimax-m2-7` | MiniMax-M2.7 | 免费 | MiniMax 文本模型 |
| `doubao-seed-2-0-lite` | Doubao-Seed-2.0-lite | 免费 | 豆包多模态 |
| `qwen3-5-plus` | Qwen3.5-Plus | 免费 | 千问原生多模态 |
| `longcat-flash-chat` | LongCat-Flash-Chat | 免费 | 美团旗舰 |
| `longcat-flash-thinking` | LongCat-Flash-Thinking | 免费 | 美团旗舰思考模型 |

> PRO 模型自动走 v3 API，免费模型走 v1 API。

## 🔌 API 使用

### OpenAI 兼容

```bash
curl http://localhost:8800/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model": "kimi-k3", "messages": [{"role": "user", "content": "你好！"}], "stream": true}'
```

### Claude Code

```bash
export ANTHROPIC_BASE_URL=http://localhost:8800
export ANTHROPIC_API_KEY=any-key-here
claude
```

### Agent 集成

| 平台 | 配置 |
|------|------|
| WorkBuddy / Trae / CodeBuddy | OpenAI Compatible Provider，BASE_URL = `http://your-server:8800/v1` |
| Cherry Studio / ChatBox | 添加 OpenAI Provider |
| Claude Code | `ANTHROPIC_BASE_URL=http://your-server:8800` |

> 管理面板 Settings → 模型管理 → 点击"测试模型更新" → 选择模型即可看到完整连接配置。

## 🎯 会话管理

| 机制 | 说明 |
|------|------|
| **自动缓存** | 同一 API Key + 模型自动共享 Tabbit room，保持对话记忆 |
| **永久会话** | 默认 TTL 7 天，room 在 Tabbit 对话列表中持久可见 |
| **固定绑定** | 手动绑定 Tabbit room → API Key，实现真正永久对话 |
| **并发锁** | 同 room 请求排队，防止 409 Conflict |
| **智能消息** | 自动过滤 WorkBuddy 标题生成指令，从超长消息提取真实问题 |
| **429 重试** | 触发限流后自动等待重试 |

### 会话管理面板

- **Sessions 页面**：查看所有活跃会话、请求次数、TTL 剩余时间
- **固定绑定**：输入 API Key + 模型 + Room ID，永久绑定
- **单个删除 / 全部清除**

## 🔧 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 服务地址 | `0.0.0.0:8800` | 监听地址与端口 |
| Tabbit 域名 | `https://web.tabbit.com` | API 目标域名（国际版填 `https://web.tabbit.ai`） |
| API Key | 空 | 全局鉴权（可选） |
| 会话缓存 | 启用 / 604800s TTL | 可关闭或调整 |

### Agent 功能开关（管理面板 Settings 页面）

| 功能 | 说明 |
|------|------|
| **消息清洗** | 过滤伪请求、去重系统消息、提取 `<user_query>` |
| **上下文管理** | 滑动窗口截断，防止超长上下文 |
| **Token 池** | 多账户轮询 + 状态机健康管理 |
| **Agent 路由** | 按 Agent 阶段选择模型 |
| **Tool Calling** | 解析并注入工具定义 |

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TABBIT_SERVER_PORT` | 监听端口 | `8800` |
| `TABBIT_BASE_URL` | Tabbit 域名 | `https://web.tabbit.com` |
| `TABBIT_API_KEY` | 全局 API Key | 空 |

## 🏗️ 架构

```
Agent (WorkBuddy/Trae/CodeBuddy)
         │
         │ OpenAI / Claude API
         ▼
    Tabbit2API (FastAPI :8800)
         │
         ├─ Agent 模块 ──────────────────────────┐
         │  ├─ Message Cleaner (消息清洗)         │
         │  ├─ Context Manager (上下文管理)       │
         │  ├─ Token Pool (Token 池)              │
         │  ├─ Agent Router (模型路由)            │
         │  └─ Tool Handler (工具调用)            │
         │                                        │
         ├─ 免费模型 → v1 API  (/api/v1/chat/completion)
         │
         └─ PRO 模型 → v3 API
               ├─ POST /panel/session
               ├─ GET  /session/{id}?_rsc
               ├─ POST /api/v3/chat/rooms/{id}/runs
               └─ POST /api/v3/chat/rooms/{id}/join (SSE)
```

## 🐳 Docker

```bash
docker compose up -d          # 启动
docker compose logs -f        # 日志
docker compose restart        # 重启
docker compose down && docker compose up -d --build  # 更新
```

## 📄 许可证

MIT License
