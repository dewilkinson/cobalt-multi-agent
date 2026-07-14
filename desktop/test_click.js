const { _electron: electron } = require('playwright');
const path = require('path');

(async () => {
  const electronApp = await electron.launch({
    executablePath: require('electron'),
    args: [path.join(__dirname, 'main.js')],
    cwd: __dirname
  });

  const window = await electronApp.firstWindow();
  
  window.on('console', msg => console.log('BROWSER_CONSOLE:', msg.type(), msg.text()));
  window.on('pageerror', error => console.error('BROWSER_ERROR:', error));

  await window.waitForLoadState('networkidle');
  console.log("App loaded.");
  
  await window.waitForSelector('#thinking-toggle', { timeout: 45000 });
  
  const textBefore = await window.locator('#thinking-badge').textContent();
  console.log("Badge before click:", textBefore);
  
  await window.locator('#thinking-toggle').click();
  console.log("Clicked thinking toggle.");
  
  await window.waitForTimeout(1000);
  
  const textAfter = await window.locator('#thinking-badge').textContent();
  console.log("Badge after click:", textAfter);
  
  await electronApp.close();
})();
