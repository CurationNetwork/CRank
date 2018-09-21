const path = require('path');
const fs = require('fs');

const args = require("args-parser")(process.argv);

if (!args.src) {
    console.log('-src not defined');
    process.exit(1);
}

const srcPath = path.resolve(__dirname, args.src);
const destPath = args.dest ? path.resolve(__dirname, args.dest) : 'out.abi';

let obj = null;
try {
    obj = JSON.parse(fs.readFileSync(srcPath, 'utf8'));
}
catch (e) {
    console.log('Cant parse source json', e);
    process.exit(1);
}

try {
    fs.writeFileSync(destPath, JSON.stringify(obj.abi));
}
catch (e) {
    console.log('Cant write into destination file', e);
    process.exit(1);
}

console.log('OK');
