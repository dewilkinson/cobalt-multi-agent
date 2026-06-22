const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

const startIdx = html.indexOf('function runSparklineAudit');
if (startIdx !== -1) {
  let braceCount = 0;
  let endIdx = -1;
  for (let i = startIdx; i < html.length; i++) {
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
    console.log(html.substring(startIdx, endIdx));
  } else {
    console.log("Function end not found");
  }
} else {
  console.log("runSparklineAudit not found");
}
