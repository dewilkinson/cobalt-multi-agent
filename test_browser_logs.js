const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture console logs
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
  page.on('response', async res => {
      if (res.url().includes('/api/scanner/bunker')) {
          console.log('BUNKER RESPONSE:', await res.json());
      }
  });

  await page.goto('http://127.0.0.1:8000/vli_dashboard.html');
  await page.waitForLoadState('domcontentloaded');

  // Find the chat input
  await page.waitForSelector('#chat-input', { timeout: 10000 });
  const chatInput = page.locator('#chat-input');

  // Type and submit
  await chatInput.fill('create new scanner');
  await chatInput.press('Enter');
  
  // Wait a few seconds for the fetch to complete and card to spawn
  await page.waitForTimeout(3000);

  // Check how many SCAN_RES windows exist
  const scanWindows = await page.$$('.card[data-type-guid="SCAN_RES"]');
  console.log('Number of SCAN_RES windows:', scanWindows.length);
  
  for (let i = 0; i < scanWindows.length; i++) {
      const rows = await scanWindows[i].$$eval('tbody tr', rows => rows.map(r => r.innerText));
      console.log(`Window ${i} has ${rows.length} rows. Content preview:`, rows.slice(0, 2));
      const selectVal = await scanWindows[i].$eval('select[id^="scan-filter-"]', el => el.value);
      console.log(`Window ${i} filter: ${selectVal}`);
  }

  await browser.close();
})();
