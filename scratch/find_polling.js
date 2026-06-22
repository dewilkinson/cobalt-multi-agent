const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

let pos = html.indexOf('vliPollingEnabled');
while (pos !== -1) {
  console.log(`Found vliPollingEnabled at index ${pos}`);
  const start = Math.max(0, pos - 150);
  const end = Math.min(html.length, pos + 150);
  console.log("--- CONTEXT ---");
  console.log(html.substring(start, end));
  console.log("---------------\n");
  pos = html.indexOf('vliPollingEnabled', pos + 1);
}
