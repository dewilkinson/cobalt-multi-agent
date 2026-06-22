const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

// Find renderWatchlist
let pos = html.indexOf('function renderWatchlist');
if (pos !== -1) {
  let braceCount = 0;
  let endIdx = -1;
  for (let i = pos; i < html.length; i++) {
    if (html[i] === '{') {
      braceCount++;
    } else if (html[i] === '}') {
      braceCount--;
      if (braceCount === 0) {
        endIdx = i + 1;
        break;
      }
    }
  }
  if (endIdx !== -1) {
    console.log(html.substring(pos, endIdx));
  } else {
    console.log("Function end not found");
  }
} else {
  console.log("renderWatchlist not found");
}
