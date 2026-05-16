let line = 'Model: BASIC [[gemini-3-flash-preview|#FF9800]]. Context: 123 chars.';
console.log(line.replace(/\[\[([^|]+)\|([^\]]+)\]\]/g, '<span style="color: $2;">($1)</span>'));
