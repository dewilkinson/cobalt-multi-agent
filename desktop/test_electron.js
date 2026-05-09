const { _electron: electron } = require('playwright');
const path = require('path');

(async () => {
  // Launch Electron app
  const electronApp = await electron.launch({
    executablePath: require('electron'),
    args: [path.join(__dirname, 'main.js')],
    cwd: __dirname
  });

  // Get the first window that the app opens
  const window = await electronApp.firstWindow();
  
  // Wait for the app to load
  await window.waitForLoadState('networkidle');
  console.log("App loaded.");
  
  // Take screenshot of initial state
  await window.screenshot({ path: 'electron_initial.png' });
  console.log("Screenshot: electron_initial.png");

  // Find the chat input box (Coordinator AI)
  await window.waitForSelector('#chat-input', { timeout: 10000 });
  const chatInput = await window.locator('#chat-input');
  
  // Type the command
  await chatInput.fill('create new scanner');
  console.log("Typed 'create new scanner'.");
  
  // Hit Enter
  await chatInput.press('Enter');
  console.log("Pressed Enter.");
  
  // Wait a few seconds for the new window to spawn
  await window.waitForTimeout(3000);
  
  // Take screenshot of final state
  await window.screenshot({ path: 'electron_final.png' });
  console.log("Screenshot: electron_final.png");

  // Check how many SCAN_RES windows exist
  const count = await window.locator('.card[data-type-guid="SCAN_RES"]').count();
  console.log("Number of SCAN_RES windows:", count);
  
  // Close the app
  await electronApp.close();
})();
