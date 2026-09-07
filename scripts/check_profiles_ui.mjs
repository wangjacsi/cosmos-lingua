// 격리 preview_profiles.py에만 연결한다. 실제 사용자 앱에는 실행하지 않는다.
import assert from 'node:assert/strict';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const {chromium} = await import(process.env.LINGUA_PLAYWRIGHT_MODULE || 'playwright');
const folder = await mkdtemp(join(tmpdir(), 'lingua-profile-ui-'));
const browser = await chromium.launch({headless: true});
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:8802');
  const form = () => page.frameLocator('iframe').locator('form#profile');
  await form().locator('[name=goal]').waitFor();
  const action = async click => {
    const response = page.waitForResponse(r => r.url().endsWith('/api/agent/action'));
    await click();
    const payload = await (await response).json();
    assert.equal(payload.ok, true);
    assert.ok(!String(payload.result).startsWith('Lingua error'));
    await form().locator('[name=goal]').waitFor();
  };
  await form().locator('[name=goal]').fill('친구와 자연스럽게 영어로 대화하기');
  await form().locator('[name=interests]').fill('코미디, 여행, 다양한 예시');
  await form().locator('[name=explanation_language]').selectOption('ko');
  await action(() => form().getByRole('button', {name: '학습 설정 저장'}).click());
  await action(() => page.getByRole('button', {name: 'B1', exact: true}).click());
  await action(() => page.getByRole('button', {name: '스페인어', exact: true}).click());
  assert.equal(await form().locator('[name=goal]').inputValue(), '');
  await action(() => page.getByRole('button', {name: '일본어', exact: true}).click());
  assert.equal(await form().locator('[name=goal]').inputValue(), '');
  await action(() => page.getByRole('button', {name: '영어', exact: true}).click());
  assert.equal(await form().locator('[name=goal]').inputValue(), '친구와 자연스럽게 영어로 대화하기');
  assert.match(await page.locator('#av-body').innerText(), /B1/);
  await page.reload();
  await form().locator('[name=goal]').waitFor();
  assert.equal(await form().locator('[name=goal]').inputValue(), '친구와 자연스럽게 영어로 대화하기');
  await page.screenshot({path: join(folder, 'settings-desktop.png')});
  const popupEvent = page.waitForEvent('popup');
  await page.locator('#av-pop').click();
  const popup = await popupEvent;
  await popup.waitForLoadState('domcontentloaded');
  assert.match(popup.url(), /#agent=lingua$/);
  await popup.frameLocator('iframe').locator('[name=goal]').waitFor();
  assert.equal(await popup.frameLocator('iframe').locator('[name=goal]').inputValue(),
    '친구와 자연스럽게 영어로 대화하기');
  await popup.screenshot({path: join(folder, 'dedicated-window.png')});
  await popup.close();
  await page.setViewportSize({width: 390, height: 844});
  await form().locator('[name=goal]').waitFor();
  const overflow = await page.locator('#av-body').evaluate(el => el.scrollWidth - el.clientWidth);
  const frameOverflow = await form().evaluate(el => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.equal(overflow, 0);
  assert.equal(frameOverflow, 0);
  await page.screenshot({path: join(folder, 'settings-mobile.png')});
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({passed: true, checks: ['form save', 'language isolation', 'level restore',
    'reload persistence', 'dedicated window', 'desktop/mobile layout', 'no page errors'], screenshots: folder}));
} finally {
  await browser.close();
}
