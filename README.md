# Tabbit2API

[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green.svg)](https://fastapi.tiangolo.com/)

**Tabbit2API** 是一个非官方的 API 适配器，专为**国内版 Tabbit 浏览器**设计。它将 Tabbit 的内部 API 转换为与 OpenAI 和 Anthropic Claude 兼容的标准化接口。

> **支持版本**：国内版 Tabbit (web.tabbit-ai.com)

## ✨ 核心功能

- **双协议兼容**：同时支持 OpenAI (`/v1/chat/completions`) 和 Anthropic Claude (`/v1/messages`) 两种主流 API 格式。
- **多账户支持**：内置 Token 池，支持添加多个 Tabbit 账户 Token，并通过轮询机制实现负载均衡。
- **智能健康管理**：自动监控 Token 状态，当某个 Token 连续出错时会进入冷却期。
- **Web 管理面板**：提供简洁直观的管理后台，用于管理 Token、查看日志、修改配置等。
- **本地快速启动**：支持 Conda 环境，无需 Docker 即可快速运行。
- **Docker 部署**：提供完整的 Docker Compose 配置，支持远程服务器部署。
- **流式与非流式**：完整支持流式（Streaming）和非流式响应。

## 🚀 快速开始

### 方式一：Docker Compose 部署（推荐用于服务器）

```bash
# 1. 克隆项目
git clone https://github.com/hoinata/tabbit2api.git
cd tabbit2api

# 2. 复制环境变量配置（可选）
cp .env.example .env

# 3. 使用 Docker Compose 启动
docker compose up -d
```

服务将在 `http://localhost:8800` 启动。首次启动会自动创建配置文件。

### 方式二：Conda 环境启动（本地开发）

```powershell
# 1. 创建并激活 Conda 环境
conda env create -f environment.yml
conda activate tabbit2api

# 2. 启动服务
python tabbit2api.py
```

### 方式三：直接使用 Python

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python tabbit2api.py
```

### 访问服务

- **API 接口**: `http://localhost:8800/v1/chat/completions`
- **管理面板**: `http://localhost:8800/admin`
- **默认密码**: `admin`

## 🔧 配置说明

### 配置文件自动生成

项目启动时会自动检查并生成配置文件：

1. 如果 `config.json` 不存在 → 自动使用默认配置创建新文件
2. 如果 `config.json` 已存在 → 加载并与默认配置合并

### 配置文件示例

项目提供了 `config.json.example` 作为配置参考，你可以手动创建配置：

```bash
# 复制示例配置
cp config.json.example config.json

# 编辑配置（添加 Tabbit Token）
vim config.json
```

### 主要配置项

| 配置项 | 路径 | 默认值 | 说明 |
|--------|------|--------|------|
| 服务主机 | `server.host` | `0.0.0.0` | 服务监听地址 |
| 服务端口 | `server.port` | `8800` | 服务监听端口 |
| Tabbit 域名 | `tabbit.base_url` | `https://web.tabbit-ai.com` | 国内版域名 |
| Client ID | `tabbit.client_id` | `2dd8eb4c1ed9c344d173` | 客户端标识 |
| 代理 API Key | `proxy.api_key` | 空 | 全局 API Key（可选） |
| 系统提示词 | `proxy.system_prompt` | 空 | 全局注入的系统提示（可选） |

### 添加 Tabbit Token

在 `tokens` 数组中添加你的 Tabbit 账户 Token：

```json
{
  "tokens": [
    {
      "id": "your-token-id",
      "name": "my-account",
      "value": "<your-tabbit-access-token>",
      "enabled": true
    }
  ]
}
```

## 🐳 Docker 部署指南

### 远程服务器部署步骤

```bash
# 1. 登录远程服务器
ssh user@your-server-ip

# 2. 安装 Docker 和 Docker Compose
# Ubuntu/Debian
sudo apt update && sudo apt install -y docker.io docker-compose-plugin

# CentOS/RHEL
sudo yum install -y docker docker-compose-plugin
sudo systemctl enable --now docker

# 3. 创建项目目录
mkdir -p /opt/tabbit2api && cd /opt/tabbit2api

# 4. 克隆项目（或上传项目文件）
git clone <repository-url> .

# 5. 启动服务
docker compose up -d

# 6. 查看日志
docker compose logs -f
```

### 自定义端口

创建 `.env` 文件：

```env
PORT=9900
TZ=Asia/Shanghai
```

或者直接指定端口启动：

```bash
PORT=9900 docker compose up -d
```

### 手动 Docker 命令

```bash
# 构建镜像
docker build -t tabbit2api .

# 运行容器
docker run -d \
  --name tabbit2api \
  --restart unless-stopped \
  -p 8800:8800 \
  -v tabbit2api_data:/app/data \
  -e TZ=Asia/Shanghai \
  tabbit2api
```

### 常用 Docker 命令

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新服务（需要重新构建）
git pull
docker compose up -d --build
```

### Nginx 反向代理配置

创建 `/etc/nginx/sites-available/tabbit2api.conf`：

```nginx
server {
    listen 80;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://localhost:8800;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持（用于流式响应）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时设置（流式响应需要较长时间）
        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/tabbit2api.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### HTTPS 配置（使用 Certbot）

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 申请 SSL 证书
sudo certbot --nginx -d api.your-domain.com

# 自动续约
sudo certbot renew --dry-run
```

## 🔌 API 端点

### OpenAI 兼容 API

**端点**: `POST /v1/chat/completions`

**示例请求**

```bash
curl http://localhost:8800/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-k2.6",
    "messages": [{"role": "user", "content": "你好！"}],
    "stream": true
  }'
```

### Claude 兼容 API

**端点**: `POST /v1/messages`

**示例请求**

```bash
curl http://localhost:8800/v1/messages \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "best",
    "messages": [{"role": "user", "content": "你好！"}],
    "stream": true
  }'
```

## 📦 支持的模型

| 模型 ID | 显示名称 | 说明 |
|---------|----------|------|
| `best` | 最佳 | 自动选择最优模型 |
| `kimi-k2.6` | Kimi-K2.6 | Moonshot 最新旗舰级多模态模型 |
| `kimi-k2.5` | Kimi-K2.5 | Moonshot 旗舰级多模态模型 |
| `glm-5.1` | GLM-5.1 | 智谱最新文本模型 |
| `glm-5v-turbo` | GLM-5V-Turbo | 智谱最新多模态模型 |
| `deepseek-v4-pro` | DeepSeek-V4-Pro | DeepSeek 旗舰模型 Pro 版 |
| `deepseek-v4-flash` | DeepSeek-V4-Flash | DeepSeek 旗舰模型 Flash 版 |
| `deepseek-v3.2` | DeepSeek-V3.2 | DeepSeek MoE 语言模型 |
| `minimax-m2.7` | MiniMax-M2.7 | MiniMax 最新旗舰级文本模型 |
| `qwen3.5-plus` | Qwen3.5-Plus | 阿里千问多模态大模型 |
| `doubao-seed-1.8` | Doubao-Seed-1.8 | 字节跳动旗舰级多模态模型 |
| `longcat-flash-chat` | LongCat-Flash-Chat | 美团自研旗舰模型 |
| `longcat-flash-thinking` | LongCat-Flash-Thinking | 美团自研旗舰思考模型 |

## 🎯 在 Cherry Studio 中配置

1. 打开 Cherry Studio → 设置 → Model Settings
2. 点击 Add Provider → Custom OpenAI Compatible API
3. 配置参数：
   - Provider Name: `Tabbit2API`
   - API Base URL: `http://your-server-ip:8800/v1`（或域名地址）
   - API Key: 留空或填写配置的 proxy.api_key
4. 添加模型（如 `kimi-k2.6`、`glm-5.1` 等）

## 🔒 安全建议

1. **修改默认密码**：登录管理面板后立即修改默认密码 `admin`
2. **设置 API Key**：在配置中设置 `proxy.api_key`，防止未授权访问
3. **启用 HTTPS**：使用 Nginx + Certbot 配置 SSL 证书
4. **限制访问**：使用防火墙限制仅允许特定 IP 访问管理面板
5. **定期更新**：定期更新项目代码和依赖

## 🎯 在 Trae 中配置

Tabbit2API 可以作为自定义模型添加到 Trae 中使用。

### 配置步骤

1. 启动 Tabbit2API 服务
   ```bash
   cd /home/tabbit
   pip install -r requirements.txt
   python tabbit2api.py
   ```

2. 打开 Trae → 设置 → 模型设置
3. 点击 **添加模型** → 选择 **自定义 OpenAI 兼容 API**
4. 配置参数：
   - **Provider Name**: `Tabbit2API`
   - **API Base URL**: `http://localhost:8800/v1`（如果部署在远程服务器，请使用服务器IP或域名）
   - **API Key**: 留空或填写配置的 `proxy.api_key`（如果已设置）
5. 添加模型：
   - 在模型列表中点击 **添加模型**
   - 输入模型 ID（如 `kimi-k2.6`、`glm-5.1`、`best` 等）
   - 模型名称可自定义

### 支持的模型列表

| 模型 ID | 显示名称 | 说明 |
|---------|----------|------|
| `best` | 最佳 | 自动选择最优模型 |
| `kimi-k2.6` | Kimi-K2.6 | Moonshot 最新旗舰级多模态模型 |
| `kimi-k2.5` | Kimi-K2.5 | Moonshot 旗舰级多模态模型 |
| `glm-5.1` | GLM-5.1 | 智谱最新文本模型 |
| `glm-5v-turbo` | GLM-5V-Turbo | 智谱最新多模态模型 |
| `deepseek-v4-pro` | DeepSeek-V4-Pro | DeepSeek 旗舰模型 Pro 版 |
| `deepseek-v4-flash` | DeepSeek-V4-Flash | DeepSeek 旗舰模型 Flash 版 |
| `deepseek-v3.2` | DeepSeek-V3.2 | DeepSeek MoE 语言模型 |
| `minimax-m2.7` | MiniMax-M2.7 | MiniMax 最新旗舰级文本模型 |
| `qwen3.5-plus` | Qwen3.5-Plus | 阿里千问多模态大模型 |
| `doubao-seed-1.8` | Doubao-Seed-1.8 | 字节跳动旗舰级多模态模型 |
| `longcat-flash-chat` | LongCat-Flash-Chat | 美团自研旗舰模型 |
| `longcat-flash-thinking` | LongCat-Flash-Thinking | 美团自研旗舰思考模型 |

### 环境变量配置

支持通过环境变量覆盖配置：

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `TABBIT_SERVER_HOST` | 服务监听地址 | `0.0.0.0` |
| `TABBIT_SERVER_PORT` | 服务监听端口 | `8800` |
| `TABBIT_BASE_URL` | Tabbit 域名 | `https://web.tabbit-ai.com` |
| `TABBIT_CLIENT_ID` | 客户端标识 | `2dd8eb4c1ed9c344d173` |
| `TABBIT_API_KEY` | 全局 API Key | 空 |
| `TABBIT_SYSTEM_PROMPT` | 全局系统提示词 | 空 |
| `TABBIT_CLAUDE_DEFAULT_MODEL` | Claude 默认模型 | `best` |
| `TABBIT_CLAUDE_SYSTEM_PROMPT` | Claude 系统提示词 | 空 |

### API 端点

- **OpenAI 兼容端点**: `POST /v1/chat/completions`
- **模型列表**: `GET /v1/models`
- **健康检查**: `GET /health`
- **管理面板**: `GET /admin`
- **Claude 兼容端点**: `POST /v1/messages`

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 🙏 参考项目

本项目参考了 [hih24337/tabb2](https://github.com/hih24337/tabb2) 的设计思路和实现方式。