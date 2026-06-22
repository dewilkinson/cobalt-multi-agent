const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

let pos = html.indexOf('UXManager.closeCard');
while (pos !== -1) {
  console.log(`Found UXManager.closeCard at index ${pos}`);
  const start = Math.max(0, pos - 150);
  const end = Math.min(html.length, pos + 150);
  console.log("--- CONTEXT ---");
  console.log(html.substring(start, end));
  console.log("---------------\n");
  pos = html.indexOf('UXManager.closeCard', pos + 1);
}
pos = html.indexOf('closeCard');
while (pos !== -1) {
  console.log(`Found closeCard at index ${pos}`);
  const start = Math.max(0, pos - 150);
  const end = Math.min(html.length, pos + 150);
  console.log("--- CONTEXT ---");
  console.log(html.substring(start, end));
  console.log("---------------\n");
  pos = html.indexOf('closeCard', pos + 1);
}
