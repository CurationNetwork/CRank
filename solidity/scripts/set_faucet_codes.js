const abi = require('ethereumjs-abi');
const fs = require('fs');

let Faucet = artifacts.require("Faucet.sol");

const hash = (code) => {
    return `0x${abi.soliditySHA3(['string'], [code]).toString('hex')}`;
};

const codesPerTx = 100;
const faucetAddress = '0xf41c3d0e08b10930ae85144a7b98231bc1f22e21';
const codesFile = 'codes.txt';

module.exports = function (callback){(async()=>{try {
    let faucet = await Faucet.at(faucetAddress);
    console.log('Faucet size:', (await faucet.faucetSize()).toString());

    let codes = fs.readFileSync(codesFile).toString().split('\n').filter(l => l.length);
    console.log('Codes loaded from file');

    let itersCnt = (codes.length / codesPerTx) + (codes.length % codesPerTx ? 1 : 0);
    for (let i = 0; i < itersCnt; ++i) {
        await faucet.setCodeHashes(codes.slice(i * codesPerTx, Math.min((i + 1) * codesPerTx, codes.length)).map(hash));
        console.log(`Uploaded ${(i/itersCnt*100).toFixed(2)}%`);
    }
    console.log('Codes was upload to contract');

    callback();
} catch (e) {console.log(e);callback(e)}})()};