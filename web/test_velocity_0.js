const parse = (v) => parseFloat(v.replace(/[$,%]/g, ''));
console.log(parse(',835.70') > parse(',831.60'));
