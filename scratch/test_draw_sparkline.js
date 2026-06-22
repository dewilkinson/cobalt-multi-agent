const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'backend', 'public', 'vli_dashboard.html');
const html = fs.readFileSync(filePath, 'utf8');

// Extract the drawSparkline function code
const startIdx = html.indexOf('function drawSparkline(');
if (startIdx === -1) {
    console.error("drawSparkline not found!");
    process.exit(1);
}

// Find the matching closing brace for the function
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

if (endIdx === -1) {
    console.error("Matching closing brace not found!");
    process.exit(1);
}

const drawSparklineCode = html.substring(startIdx, endIdx);
console.log("--- Extracted drawSparkline Code ---");
console.log(drawSparklineCode);
console.log("------------------------------------\n");

// Eval the function
eval(drawSparklineCode);

// Test 1: plain numbers
try {
    const res1 = drawSparkline([100, 105, 110], "SPY");
    console.log("Test 1 (numbers) succeeded:\n", res1);
} catch (e) {
    console.error("Test 1 failed:", e);
}

// Test 2: objects
try {
    const res2 = drawSparkline([
        { v: 100, is_prev: true },
        { v: 105, is_prev: true },
        { v: 110, is_prev: false }
    ], "SPY");
    console.log("Test 2 (objects) succeeded:\n", res2);
} catch (e) {
    console.error("Test 2 failed:", e);
}

// Test 3: empty/sparse
try {
    const res3 = drawSparkline([null, null], "SPY");
    console.log("Test 3 (all nulls) succeeded:\n", res3);
} catch (e) {
    console.error("Test 3 failed:", e);
}
