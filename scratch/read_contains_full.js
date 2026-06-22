const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

const pos = html.indexOf('.card-header:contains("MACRO WATCHLIST")');
if (pos !== -1) {
  const start = Math.max(0, pos - 500);
  const end = Math.min(html.length, pos + 500);
  console.log(html.substring(start, end));
} else {
  console.log("Not found");
}
