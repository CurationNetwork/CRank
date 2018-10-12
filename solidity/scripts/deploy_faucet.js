let Faucet = artifacts.require("Faucet.sol");

const tokenAddress = '0xdd5c07c484778ae52b5e60999bf625a998c265b4';
const adminAddress = '0x5787a154825341b64673c99b0eb72220f32da7f0';
let faucetSize = web3.toWei(1000);
let charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';



module.exports = function (callback) {(async () => {try {
    let faucet = await Faucet.new(adminAddress);
    console.log('Faucet deployed, address:', faucet.address);

    await faucet.init(tokenAddress);
    await faucet.setFaucetSize(faucetSize);
    await faucet.setCharset(charset);

    console.log('Faucet initialized');

    callback();
}catch (e){console.log(e);callback(e)}})()};