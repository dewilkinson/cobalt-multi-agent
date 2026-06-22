const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

// Find all matches for fetch or api URLs
const fetchRegex = /fetch\(([^)]+)\)/gi;
let match;
console.log("=== FETCH CALLS ===");
while ((match = fetchRegex.exec(html)) !== null) {
  console.log(match[0]);
}

console.log("\n=== EVENT SOURCE / WEBSOCKET ===");
const connRegex = /(EventSource|WebSocket)\(([^)]+)\)/gi;
while ((match = connRegex.exec(html)) !== null) {
  console.log(match[0]);
}

console.log("\n=== FUNCTION NAMES ===");
const funcRegex = /function\s+(\w+)\s*\(/g;
const funcs = [];
while ((match = funcRegex.exec(html)) !== null) {
  funcs.push(match[1]);
}
console.log(funcs.join(', '));
