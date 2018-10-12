const BigNumber = web3.BigNumber;
const { expectThrow } = require('../node_modules/zeppelin-solidity/test/helpers/expectThrow');

const toWei = web3.toWei;
const abi = require('ethereumjs-abi');
const chai =require('chai');
chai.use(require('chai-bignumber')(BigNumber));
chai.use(require('chai-as-promised')); // Order is important
chai.should();

const Ranking = artifacts.require('Ranking');
const Faucet = artifacts.require('Faucet');
const Voting = artifacts.require('Voting');
const Admin = artifacts.require('Admin');

const fromWei = (num) => {
    if (typeof num === 'string' || typeof num === 'number')
        return web3.fromWei(num);
    return web3.fromWei(num.toString());
};

const hash = (code) => {
    return `0x${abi.soliditySHA3(['string'], [code]).toString('hex')}`;
};

const genCode = (charset) => {
    let res = '';
    for (let i = 0; i < 7; i++)
        res += charset.charAt(Math.floor(Math.random() * charset.length));

    return res;
};


const getRandomAscii = (length) => {
    let res = '';
    for (let i = 0; i < length; i++)
        res += String.fromCharCode(Math.floor(Math.random() * 255));

    return res;
};


contract('Faucet', function(accounts) {
    let charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let totalSupply = toWei(1000000);
    let faucetSize = toWei(1000);
    let codesCnt = 20;

    let rankingParams = [ 1, 100, 100, 1, 10, toWei(0.5), 180, 180, toWei(300) ];

    describe('full', function() {
        before(async function () {
            this.admin = await Admin.new();
            this.token = await Ranking.new(this.admin.address);
            this.faucet = await Faucet.new(this.admin.address);
            this.voting = await Voting.new();

            await this.token.init(this.voting.address, ...rankingParams);

            await this.faucet.init(this.token.address);
            await this.faucet.setFaucetSize(faucetSize);
            await this.token.transfer(this.faucet.address, totalSupply);
            await this.faucet.getBalance().should.eventually.be.bignumber.equal(totalSupply);
        });

        let codes = [];

        it('set charset', async function () {
            await this.faucet.setCharset(charset);
        });

        it('set codes', async function () {
            for (let i = 0; i < codesCnt; i++) {
                let code = genCode(charset);
                if (codes.find(c => c === code)) {
                    --i;
                    continue;
                }
                codes.push(code);
            }

            await this.faucet.setCodeHashes(codes.map(hash));
        });

        it('faucet with valid code', async function () {
            for (let i = 0; i < codesCnt / 2; i++) {
                let senderBalanceBefore = await this.token.balanceOf(accounts[2]);
                let faucetBalanceBefore = await this.faucet.getBalance();
                await this.faucet.faucet(codes[i], {from: accounts[2]});
                await this.token.balanceOf(accounts[2]).should.eventually.be.bignumber.equal(senderBalanceBefore.add(faucetSize));
                await this.faucet.getBalance().should.eventually.be.bignumber.equal(faucetBalanceBefore.sub(faucetSize));
            }
        });

        it('faucet with incorrect code', async function () {
            expectThrow(this.faucet.faucet(genCode(charset), {from: accounts[2]}));
        });

        it('faucet with invalid code', async function () {
            expectThrow(this.faucet.faucet(getRandomAscii(Math.random()*10), {from: accounts[2]}));
            expectThrow(this.faucet.faucet(getRandomAscii(Math.random()*10), {from: accounts[2]}));
            expectThrow(this.faucet.faucet(getRandomAscii(Math.random()*10), {from: accounts[2]}));
            expectThrow(this.faucet.faucet(getRandomAscii(Math.random()*10), {from: accounts[2]}));
        });

        it('destruct', async function () {
            let faucetBalance = await this.faucet.getBalance();
            let ownerBalance = await this.token.balanceOf(accounts[0]);
            await this.faucet.destruct({from: accounts[0]});
            await this.token.balanceOf(accounts[0]).should.eventually.be.bignumber.equal(ownerBalance.add(faucetBalance));
        });
    })
});
