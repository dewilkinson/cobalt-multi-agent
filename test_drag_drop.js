const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));

  await page.goto('http://127.0.0.1:8000/vli_dashboard.html');
  await page.waitForLoadState('domcontentloaded');

  const chatInput = page.locator('#chat-input');
  await chatInput.fill('show NVDA analysis');
  await chatInput.press('Enter');
  
  await page.waitForTimeout(5000);

  const cards = await page.locator('.card').all();
  let targetCard = null;
  for (let card of cards) {
      const title = await card.locator('.card-header > div > div:nth-child(2)').first().innerText().catch(() => '');
      if (title.includes('NVDA')) {
          targetCard = card;
          break;
      }
  }

  if (!targetCard) {
      console.log('Failed to find NVDA card');
      await browser.close();
      return;
  }
  
  const artifactPath = await targetCard.getAttribute('data-artifact-path');
  console.log("Card path:", artifactPath);

  await page.evaluate(() => {
    document.querySelectorAll('.tree-folder').forEach(f => f.classList.add('open'));
  });

  await page.waitForTimeout(1000);

  const notesFolder = await page.locator('.tree-folder[data-path*="Notes"]').first();
  const notesLabel = notesFolder.locator('.tree-label').first();
  
  console.log("Target Notes Folder Text:", await notesLabel.innerText());

  const cardHeader = targetCard.locator('.card-header').first();
  const cardHeaderBox = await cardHeader.boundingBox();
  const notesBox = await notesLabel.boundingBox();

  console.log("Header box:", cardHeaderBox);
  console.log("Notes box:", notesBox);

  await page.mouse.move(cardHeaderBox.x + 10, cardHeaderBox.y + 10);
  await page.mouse.down();
  
  await page.waitForTimeout(500);

  await page.mouse.move(notesBox.x + 10, notesBox.y + 5, { steps: 20 });
  
  await page.waitForTimeout(500);
  
  const elemUnder = await page.evaluate(({x, y}) => {
      const e = document.elementFromPoint(x, y);
      return e ? e.className : null;
  }, {x: notesBox.x + 10, y: notesBox.y + 5});
  console.log("Elem under cursor before mouseup:", elemUnder);

  await page.mouse.up();

  await page.waitForTimeout(2000);

  await browser.close();
})();
