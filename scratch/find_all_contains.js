const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

const regex = /:contains\b/g;
let match;
while ((match = regex.exec(html)) !== null) {
  const pos = match.index;
  const start = Math.max(0, pos - 150);
  const end = Math.min(html.length, pos + 150);
  console.log("Found :contains context at index:", pos);
  console.log(html.substring(start, end));
  console.log("---------------------------------\n");
}
