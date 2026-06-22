const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  console.log("Launching Chromium browser with no-sandbox flags...");
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture console logs
  page.on('console', msg => {
    console.log(`[BROWSER LOG (${msg.type()})]:`, msg.text());
  });

  page.on('pageerror', err => {
    console.error('[BROWSER ERROR]:', err.message, err.stack);
  });

  console.log("Navigating to dashboard with 60s timeout...");
  try {
    await page.goto('http://127.0.0.1:8000/vli_dashboard.html', {
      waitUntil: 'load',
      timeout: 60000
    });
    console.log("Navigation loaded successfully.");
  } catch (err) {
    console.error("Navigation failed/timed out:", err.message);
  }

  console.log("Waiting 5 seconds for any post-load rendering...");
  await page.waitForTimeout(5000);

  // Print DOM structure preview
  const bodyText = await page.evaluate(() => {
    return {
      bodyLength: document.body.innerHTML.length,
      visibleText: document.body.innerText.substring(0, 500),
      cardsCount: document.querySelectorAll('.card').length,
      cardHeaders: Array.from(document.querySelectorAll('.card-header')).map(el => el.innerText),
      verifyBtnExists: !!document.getElementById('verify-audit-btn')
    };
  });
  console.log("DOM state preview:", JSON.stringify(bodyText, null, 2));

  // Save screenshot of current state
  const screenshotPath = path.join(__dirname, '..', 'artifacts', 'sparkline_debug_full_load.png');
  const artifactsDir = path.dirname(screenshotPath);
  if (!fs.existsSync(artifactsDir)) {
    fs.mkdirSync(artifactsDir, { recursive: true });
  }
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log("Saved screenshot to", screenshotPath);

  // If cards are found, let's see if we can trigger the sparkline audit!
  if (bodyText.cardsCount > 0) {
    console.log("Cards found. Looking for verify button...");
    const hasAuditBtn = await page.evaluate(() => {
      const btn = document.getElementById('verify-audit-btn');
      if (btn) {
        btn.click();
        return true;
      }
      return false;
    });

    if (hasAuditBtn) {
      console.log("Clicked verify-audit-btn! Waiting 15s for audit to run...");
      await page.waitForTimeout(15000);
      
      const svgTickers = await page.$$eval('svg[data-ticker]', svgs => {
        return svgs.map(svg => ({
          ticker: svg.getAttribute('data-ticker'),
          width: svg.getAttribute('width'),
          height: svg.getAttribute('height')
        }));
      });
      console.log("Rendered sparklines:", JSON.stringify(svgTickers, null, 2));
      
      const afterAuditScreenshot = path.join(__dirname, '..', 'artifacts', 'sparkline_after_audit.png');
      await page.screenshot({ path: afterAuditScreenshot, fullPage: true });
      console.log("Saved post-audit screenshot to", afterAuditScreenshot);
    } else {
      console.log("Verify audit button not found.");
    }
  } else {
    // If no cards found, let's trigger default layout load
    console.log("No cards found in DOM. Manually triggering loadLayout()...");
    await page.evaluate(() => {
      if (typeof loadLayout === 'function') {
        loadLayout();
      }
    });
    await page.waitForTimeout(3000);
    
    const bodyText2 = await page.evaluate(() => {
      return {
        cardsCount: document.querySelectorAll('.card').length,
        cardHeaders: Array.from(document.querySelectorAll('.card-header')).map(el => el.innerText)
      };
    });
    console.log("DOM state after loadLayout():", JSON.stringify(bodyText2, null, 2));
    
    const manualLoadScreenshot = path.join(__dirname, '..', 'artifacts', 'sparkline_manual_load.png');
    await page.screenshot({ path: manualLoadScreenshot, fullPage: true });
    console.log("Saved manual-load screenshot to", manualLoadScreenshot);
  }

  await browser.close();
  console.log("Browser closed. Test finished.");
})();
