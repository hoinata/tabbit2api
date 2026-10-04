#!/usr/bin/env node
/**
 * get_tabbit_token.mjs — 从本机已登录的 Tabbit 浏览器中导出 Tabbit2API 所需的 Access Token
 *
 * 原理：Tabbit 基于 Chromium，登录后会在 `web.tabbit.ai` 域下写入 `token` Cookie（一个 JWT）。
 *       本脚本用 Playwright 以「复制的已登录 profile」启动 Tabbit 内核，直接读取 Cookie，
 *       拼成 Tabbit2API 需要的 `token|next-auth.session-token|device_id` 形式（缺失段可省略）。
 *
 * 依赖：node >= 18，playwright-core（或 playwright）
 *   npm i -D playwright-core
 *
 * 用法（macOS 为例，先完全退出 Tabbit 应用）：
 *   node tools/get_tabbit_token.mjs
 *   node tools/get_tabbit_token.mjs --profile "/path/to/Tabbit profile copy"
 *   node tools/get_tabbit_token.mjs --app "/Applications/Tabbit.app/Contents/MacOS/Tabbit"
 *
 * 注意：
 *   - 脚本会先把 profile 复制到临时目录再读取，避免占用/锁住正在运行的 Tabbit。
 *   - 输出的 token 是敏感凭证，请勿泄露；有效期约 7 天，过期后重新运行即可。
 */
import { chromium } from 'playwright-core';
import { cpSync, rmSync, mkdtempSync, existsSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';
import { join } from 'node:path';

function arg(name, def) {
  const i = process.argv.indexOf(`--${name}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const HOME = homedir();
const DEFAULT_PROFILE =
  process.platform === 'darwin'
    ? join(HOME, 'Library/Application Support/Tabbit')
    : process.platform === 'win32'
      ? join(process.env.LOCALAPPDATA || '', 'Tabbit', 'User Data')
      : join(HOME, '.config/Tabbit');
const DEFAULT_APP =
  process.platform === 'darwin'
    ? '/Applications/Tabbit.app/Contents/MacOS/Tabbit'
    : undefined;

const profileSrc = arg('profile', DEFAULT_PROFILE);
const appPath = arg('app', DEFAULT_APP);
const site = arg('site', 'https://web.tabbit.ai');

if (!existsSync(profileSrc)) {
  console.error(`找不到 profile 目录: ${profileSrc}`);
  process.exit(1);
}

const work = mkdtempSync(join(tmpdir(), 'tabbit-tok-'));
const profileCopy = join(work, 'profile');
console.log(`复制 profile: ${profileSrc}\n         -> ${profileCopy}`);
cpSync(profileSrc, profileCopy, { recursive: true });
for (const lock of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
  try { rmSync(join(profileCopy, lock), { force: true }); } catch {}
}

const ctx = await chromium.launchPersistentContext(profileCopy, {
  executablePath: appPath,
  headless: true,
  // 关键：默认参数里的 --use-mock-keychain 会让 Chromium 用假钥匙串，
  // 读不出用真实 "<App> Safe Storage" 加密的 Cookie（整库被丢弃）。必须移除。
  ignoreDefaultArgs: ['--use-mock-keychain'],
  args: ['--no-first-run', '--no-default-browser-check'],
});

const cookies = {};
for (const c of await ctx.cookies(site)) cookies[c.name] = c.value;
await ctx.close();
rmSync(work, { recursive: true, force: true });

const jwt = cookies['token'] || '';
const nextAuth = cookies['next-auth.session-token'] || '';
if (!jwt) {
  console.error('未找到 web.tabbit.ai 的 `token` Cookie —— 请确认已在 Tabbit 中登录该站点。');
  process.exit(2);
}

const value = [jwt, nextAuth].filter(Boolean).join('|');
console.log('\n=== Tabbit2API Token（粘贴到管理面板 Tokens 页）===');
console.log(value);
console.log('\n说明：user_id 无需填写，程序会从 JWT 自动解析。');
