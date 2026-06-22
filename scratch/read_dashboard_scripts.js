const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

// Find all script tags
const scriptRegex = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
const srcRegex = /src=["']([^"']+)["']/i;
let match;
console.log("=== SCRIPT TAGS ===");
while ((match = scriptRegex.exec(html)) !== null) {
  const fullTag = match[0];
  const srcMatch = srcRegex.exec(fullTag);
  if (srcMatch) {
    console.log("External Script:", srcMatch[1]);
  } else {
    console.log("Inline Script (length):", match[1].length);
  }
}

console.log("\n=== LINK TAGS ===");
const linkRegex = /<link\b[^>]*>/gi;
const hrefRegex = /href=["']([^"']+)["']/i;
while ((match = linkRegex.exec(html)) !== null) {
  const fullTag = match[0];
  const hrefMatch = hrefRegex.exec(fullTag);
  if (hrefMatch) {
    console.log("Link href:", hrefMatch[1]);
  }
}
