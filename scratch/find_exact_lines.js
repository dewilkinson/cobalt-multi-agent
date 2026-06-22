const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

function findLine(target) {
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes(target)) {
      console.log(`Line ${i + 1}: ${lines[i].trim()}`);
    }
  }
}

console.log("=== Target 1: contains ===");
findLine('.card-header:contains("MACRO WATCHLIST")');

console.log("\n=== Target 2: vliPollingEnabled ===");
findLine('let vliPollingEnabled = true;');

console.log("\n=== Target 3: updateCountdown ===");
findLine("document.getElementById('macro-timer').innerText =");

console.log("\n=== Target 4: closeCard ===");
findLine('UXManager.closeCard');
