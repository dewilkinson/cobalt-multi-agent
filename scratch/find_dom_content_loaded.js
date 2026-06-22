const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

// Find all DOMContentLoaded listeners
let pos = html.indexOf('DOMContentLoaded');
while (pos !== -1) {
  console.log(`Found DOMContentLoaded at index ${pos}`);
  const start = Math.max(0, pos - 200);
  const end = Math.min(html.length, pos + 400);
  console.log("--- CONTEXT ---");
  console.log(html.substring(start, end));
  console.log("---------------\n");
  pos = html.indexOf('DOMContentLoaded', pos + 1);
}
