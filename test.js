// test.js

var x = 1       // 'var' is outdated, should be 'let' or 'const'
console.log(x)  // missing semicolon

function testFunc(a,b){console.log(a+b)}  // missing space after comma, could enforce spacing rules

testFunc(2,3)
