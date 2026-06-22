const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

function printRange(start, end) {
  console.log(`--- Lines ${start} to ${end} ---`);
  for (let i = start - 1; i < end; i++) {
    console.log(`${i + 1}: ${lines[i]}`);
  }
}

printRange(3448, 3456);
printRange(5135, 5143);
printRange(5793, 5801);
printRange(6083, 6091);
printRange(6180, 6188);
