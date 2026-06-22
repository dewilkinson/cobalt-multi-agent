const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

// Get the body content
const bodyStart = html.indexOf('<body');
const bodyEnd = html.indexOf('</body>');
if (bodyStart !== -1 && bodyEnd !== -1) {
  const body = html.substring(bodyStart, bodyEnd + 7);
  // Remove scripts from body printout for readability
  const cleanBody = body.replace(/<script\b[^>]*>([\s\S]*?)<\/script>/gi, '<!-- SCRIPT REMOVED -->');
  console.log(cleanBody);
} else {
  console.log("Body not found");
}
