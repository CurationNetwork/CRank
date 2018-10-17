let Voting = artifacts.require("./Voting.sol");
let Ranking = artifacts.require("./Ranking.sol");
let Faucet = artifacts.require("./Faucet.sol");
let Admin = artifacts.require("./Admin.sol");
let Token = artifacts.require("./Token.sol");

//unstakeSpeed, currentCommitTtl, currentRevealTtl, initialAvgStake
let rankingParams = [web3.toWei(0.05), 30, 30, web3.toWei(0)];

// dynamicFeeLinearRate, dynamicFeeLinearPrecision, maxOverStakeFactor, maxFixedFeeRate, maxFixedFeePrecision,
let votingParams = [2, 100, 100, 2, 100];

let totalSupply = web3.toWei(1000000);
let faucetCharset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
let faucetSize = web3.toWei(1000);


module.exports = async function(deployer) {
    let voting, ranking, faucet, admin, token;

    deployer.then(function() {
        return Admin.new();
    }).then(function(instance) {
        admin = instance;
        console.log('Admin:', admin.address);

        return Voting.new(admin.address);
    }).then(function(instance) {
        voting = instance;
        console.log('Voting:', voting.address);

        return Token.new();
    }).then(function(instance) {
        token = instance;
        console.log('Token:', token.address);

        return Ranking.new(admin.address);
    }).then(function(instance) {
        ranking = instance;
        console.log('Ranking:', ranking.address);

        return Faucet.new(admin.address);
    }).then(function(instance) {
        faucet = instance;
        console.log('Faucet:', faucet.address);

        return ranking.init(voting.address, token.address, ...rankingParams);
    }).then(async function () {
        console.log('Ranking inited');

        return voting.init(ranking.address, ...votingParams);
    }).then(async function () {
        console.log('Voting inited');

        return faucet.init(ranking.address);
    }).then(async function () {
        console.log('Faucet inited');

        return faucet.setFaucetSize(faucetSize);
    }).then(async function () {
        console.log('Faucet size');

        return faucet.setCharset(faucetCharset);
    }).then(async function () {
        console.log('Faucet charset');

        return token.transfer(faucet.address, totalSupply);
    }).then(async function () {
        console.log('Faucet charged');
    })
    .catch(e => console.log(e));

};
