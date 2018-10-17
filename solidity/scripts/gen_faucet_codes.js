const genCode = (charset) => {
    let res = '';
    for (let i = 0; i < 7; i++)
        res += charset.charAt(Math.floor(Math.random() * charset.length));

    return res;
};

const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
const codesCnt = 1000;

let codes = new Set();

module.exports = function (done) {
    while (codes.size < codesCnt) {
        let code = genCode(charset);
        if (!codes.has(code)) {
            console.log(code);
            codes.add(code);
        }
    }

    done();
};