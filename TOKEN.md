# 如何获取 Tabbit Access Token

Tabbit2API 通过 **Token 池** 调用 Tabbit 网页端，需要在管理面板里为每个 Tabbit 账号添加一个 **Access Token**。
本文说明这个 Token 是什么、怎么取、放哪里。

> 支持域名：国内版 `web.tabbit.com` / 国际版 `web.tabbit.ai`（两个均为官方站点，主要差别是内置模型与数据区域）。Token 与所登录的 Tabbit 站点绑定，请确保在**同一站点**下登录并导出，并把 `base_url` 配成对应域名。

---

## 一、Token 是什么

Tabbit 基于 Chromium。登录网页端后，`web.tabbit.ai` / `web.tabbit.com` 域下会写入名为 **`token`** 的 Cookie，其值为一个 **JWT**（`eyJ...` 三段式）。

Tabbit2API 接受的值格式为竖线分隔的三段（**只有第一段必需**）：

```
<jwt_token> | <next-auth.session-token?> | <device_id?>
```

| 段 | 来源 | 是否必需 |
|----|------|----------|
| `jwt_token` | Cookie `token` 的值 | ✅ 必需 |
| `next-auth.session-token` | Cookie `next-auth.session-token` | 可选 |
| `device_id` | 任意 UUID | 可选（缺省自动生成） |

- **`user_id` 无需填写**：程序会从 JWT 的 payload 里自动解析（`id` / `sub`）。
- 也就是说：**最少只需把 Cookie `token` 的 JWT 粘进去**即可。

---

## 二、获取方式

### 方式 A：直接从浏览器复制（最简单）

1. 用 Tabbit 打开并登录对应站点（如 `https://web.tabbit.ai`）。
2. 打开开发者工具（F12 / ⌥⌘I）→ **Application / 应用** → **Cookies** → 选择该站点域名。
3. 找到名为 `token` 的条目，复制它的 **Value**（`eyJ...` 开头的 JWT）。
4. 打开 Tabbit2API 管理面板 → **Tokens 管理** → **添加 Token**：
   - **名称**：便于识别的账号名（如 `my-main-account`）
   - **值**：粘贴上面复制的 JWT（如需，用 `|` 追加 `next-auth.session-token`）

### 方式 B：脚本自动导出（跨平台，推荐）

仓库提供 `tools/get_tabbit_token.mjs`，用 Playwright 以「复制的已登录 profile」启动 Tabbit 内核并读出 Cookie。

```bash
# 依赖
npm i -D playwright-core

# 先完全退出 Tabbit 应用，然后：
node tools/get_tabbit_token.mjs
# 可选参数：
#   --profile "/path/to/Tabbit"            自定义 profile 路径
#   --app "/Applications/Tabbit.app/Contents/MacOS/Tabbit"   自定义内核可执行文件
#   --site "https://web.tabbit.ai"         指定读取哪个域名
```

输出即为可直接粘贴的 Token 值。
脚本会自动把 profile 复制到临时目录再读取，不会占用/锁住正在运行的 Tabbit。

### 方式 C：手动解密 Cookie 数据库（进阶）

Chromium 在 macOS 上用 Keychain 中的 `Tabbit Safe Storage` 派生密钥、AES-128-CBC、密文前缀 `v10`，IV 为 16 空格。
各版本 Tabbit 构建细节可能不同，**不建议手搓**；优先用方式 A / B。

---

## 三、添加与管理

- 管理面板 → **Tokens 管理**：可添加 / 删除 / 编辑 / 启停 Token。
- 池中 Token 采用**加权轮询**，配合 `ACTIVE / COOLDOWN / BANNED` 状态机做健康管理：某个 Token 连续出错会进入冷却期，自动切换其它 Token。
- 可选配置 `encryption_key`（见 `config.json` 的 `agent.token_pool`），用 Fernet 加密存储 Token。

## 四、常见问题

| 现象 | 原因 / 处理 |
|------|-------------|
| 返回 `请先登录`（401） | Token 无效或与当前 `base_url` 站点不匹配 —— 重新登录对应域名并导出 |
| 返回「浏览器版本过低」(code 493) | 用的是旧接口/旧客户端协议，升级 Tabbit 客户端或改用当前接口 |
| Token 突然失效 | JWT 过期（约 7 天），重新导出即可 |
| 脚本读到 0 个 cookie / 明明登录了却「未找到 token」 | Playwright 默认 `--use-mock-keychain` 用假钥匙串，读不出系统真实加密的 cookie。脚本已加 `ignoreDefaultArgs: ['--use-mock-keychain']`；若仍失败，确认已在**同一台机器**的 Tabbit 里登录过目标域名 |
| 多账号 | 每个账号单独导出一个 Token，全部加入 Token 池 |

> ⚠️ Token 等同账号凭证，请勿公开分享或提交到仓库。
