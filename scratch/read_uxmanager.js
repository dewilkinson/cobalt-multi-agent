const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

const pos = html.indexOf('const UXManager =');
if (pos !== -1) {
  const start = pos;
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
    console.log("UXManager end not found");
  }
} else {
  // Let's search for just "UXManager"
  let searchPos = html.indexOf('UXManager');
  while (searchPos !== -1) {
    console.log("Found UXManager at index:", searchPos);
    const start = Math.max(0, searchPos - 50);
    const end = Math.min(html.length, searchPos + 100);
    console.log(html.substring(start, end));
    searchPos = html.indexOf('UXManager', searchPos + 1);
  }
}
