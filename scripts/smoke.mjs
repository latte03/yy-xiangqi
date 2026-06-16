import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox'],
  });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  const errors = [];
  const consoleMsgs = [];
  page.on('pageerror', (e) => errors.push(`PAGEERROR: ${e.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`CONSOLE.ERROR: ${msg.text()}`);
    consoleMsgs.push(`[${msg.type()}] ${msg.text()}`);
  });
  page.on('worker', (w) => {
    w.on('console', (msg) => {
      consoleMsgs.push(`[worker:${w.url().slice(-30)}] [${msg.type()}] ${msg.text()}`);
    });
  });

  await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  console.log('=== After load ===');
  console.log('Errors:', errors.length);
  console.log('Console msgs:', consoleMsgs.length);

  // 切到对战模式
  console.log('=== Switch to play mode ===');
  await page.click('label:has-text("对战")');
  await page.waitForTimeout(800);
  const mode1 = await page.locator('input[type="radio"]:checked').first().getAttribute('value').catch(() => '?');
  console.log('Mode radio:', mode1);

  // 看 play 模式可见的"走法记录"面板
  const movePanelCount = await page.locator('.moves').count();
  console.log('Move panels:', movePanelCount);

  // 找 "AI 先手开局" 按钮
  const aiBtns = await page.locator('button:has-text("AI 先手开局")').count();
  console.log('AI 先手开局 buttons:', aiBtns);

  // 点击 AI 先手开局
  await page.click('button:has-text("AI 先手开局")');
  console.log('Clicked AI 先手开局, waiting 15s...');
  await page.waitForTimeout(15000);

  // 状态
  const fen = await page.locator('code.fen').textContent().catch(() => '(no fen)');
  console.log('FEN:', fen?.slice(0, 80));
  const moves = await page.locator('.moves .move').count();
  console.log('Moves count:', moves);
  const overlay = await page.locator('.ai-overlay').count();
  console.log('AI overlay (thinking):', overlay);
  const err = await page.locator('.ai-error').textContent().catch(() => null);
  console.log('AI error:', err);

  console.log('=== Final ===');
  console.log('Total errors:', errors.length);
  errors.forEach((e) => console.log('  ', e));
  consoleMsgs.slice(-30).forEach((m) => console.log('  ', m));

  await browser.close();
  process.exit(errors.length > 0 ? 1 : 0);
})().catch((e) => {
  console.error('TEST FAILED:', e);
  process.exit(1);
});