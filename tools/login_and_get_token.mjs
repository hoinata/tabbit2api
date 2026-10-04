#!/usr/bin/env node
/**
 * login_and_get_token.mjs v2 — 打开可见 Tabbit 窗口登录并导出 Token（加固版）
 *   - 窗口关闭/出错不再崩溃
 *   - 自动把窗口置顶
 *   - 同时检查 web.tabbit.ai 与 web.tabbit.com
 *   - token 落盘到 /tmp/tabbit_token.txt
 */
import { chromium } from 'playwright-core';
import { cpSync, rmSync, mkdtempSync, existsSync, writeFileSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';
import { join } from 'node:path';

const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i !== -1 && process.argv[i+1] ? process.argv[i+1] : d; };
const HOME = homedir();
const profileSrc = arg('profile', join(HOME, 'Library/Application Support/Tabbit'));
const appPath = arg('app', '/Applications/Tabbit.app/Contents/MacOS/Tabbit');
const site = arg('site', 'https://web.tabbit.ai');
const altSite = arg('alt', 'https://web.tabbit.com');
const timeoutSec = parseInt(arg('timeout', '900'), 10);

if (!existsSync(profileSrc)) { console.error('找不到 profile: ' + profileSrc); process.exit(1); }

const work = mkdtempSync(join(tmpdir(), 'tabbit-login-'));
const profileCopy = join(work, 'profile');
console.log(`复制 profile: ${profileSrc} -> ${profileCopy}`);
cpSync(profileSrc, profileCopy, { recursive: true });
for (const lock of ['SingletonLock','SingletonCookie','SingletonSocket']) { try { rmSync(join(profileCopy, lock), { force: true }); } catch {} }

const ctx = await chromium.launchPersistentContext(profileCopy, {
  executablePath: appPath, headless: false,
  args: ['--no-first-run','--no-default-browser-check'],
});

let closed = false;
ctx.on('close', () => { closed = true; });

async function grabToken(fromSite) {
  const cks = await ctx.cookies(fromSite).catch(() => []);
  const t = cks.find(c => c.name === 'token');
  const n = cks.find(c => c.name === 'next-auth.session-token');
  return t && t.value ? { jwt: t.value, nextAuth: n ? n.value : '' } : null;
}

const page = ctx.pages()[0] || await ctx.newPage();
await page.goto(site + '/login', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
await page.bringToFront().catch(() => {});
console.log('\n========================================');
console.log(' 请在弹出的 Tabbit 窗口中完成 Google 登录');
console.log(` 站点: ${site}（登录成功后自动抓取，最多等 ${timeoutSec}s）`);
console.log('========================================\n');

const deadline = Date.now() + timeoutSec * 1000;
let found = null;
try {
  while (Date.now() < deadline && !closed) {
    found = await grabToken(site) || await grabToken(altSite);
    if (found) break;
    await page.waitForTimeout(2000).catch(() => {});
  }
} catch (e) { console.error('轮询结束:', e.message); }

if (!found) {
  console.error('\n未获取到 token（超时或窗口已关闭）。');
  try { await ctx.close(); } catch {}
  rmSync(work, { recursive: true, force: true });
  process.exit(2);
}

const value = [found.jwt, found.nextAuth].filter(Boolean).join('|');
writeFileSync('/tmp/tabbit_token.txt', value);
console.log('\n=== Tabbit2API Token（已存 /tmp/tabbit_token.txt）===');
console.log(value);
console.log('\ntoken 长度 ' + found.jwt.length + '，有效期约 7 天');

try { await ctx.close(); } catch {}
rmSync(work, { recursive: true, force: true });
process.exit(0);
