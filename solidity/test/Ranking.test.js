const BigNumber = web3.BigNumber;
const { latestTime } = require('../node_modules/zeppelin-solidity/test/helpers/latestTime');
const { increaseTimeTo, duration } = require('../node_modules/zeppelin-solidity/test/helpers/increaseTime');
const { advanceBlock } = require('../node_modules/zeppelin-solidity/test/helpers/advanceToBlock');
const { expectThrow } = require('../node_modules/zeppelin-solidity/test/helpers/expectThrow');

const toWei = web3.toWei;
const chai =require('chai');
chai.use(require('chai-bignumber')(BigNumber));
chai.use(require('chai-as-promised')); // Order is important
chai.should();

const Token = artifacts.require('Token');
const Voting = artifacts.require('Voting');
const Ranking = artifacts.require('Ranking');
const Helper = artifacts.require('Helper');
const Admin = artifacts.require('Admin');

const fromWei = (num) => {
    if (typeof num === 'string' || typeof num === 'number')
        return web3.fromWei(num);
    return web3.fromWei(num.toString());
};


contract('Ranking', function(accounts) {

    let voters = accounts.slice(2, 5);
    let commissions = voters.map(() => new BigNumber(0));
    let initialBalance = toWei(10000);
    let votingParams = [2, 100, 100, 2, 100];
    let rankingParams = [toWei(1), 180, 180, toWei(0)];

    let defaultRanks = [toWei(300), toWei(250), toWei(200)];

    describe('full', function() {

        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);
        });

        let startTime = null;

        it('add items', async function() {
            await this.ranking.newItem(1, defaultRanks[0], accounts[0]);
            await this.ranking.newItem(2, defaultRanks[1], accounts[0]);
            await this.ranking.newItem(3, defaultRanks[2], accounts[0]);

            (await this.ranking.getItemsWithRank.call())[0].length.should.be.equal(3);
            (await this.ranking.getItemsWithRank.call())[1].length.should.be.equal(3);
        });

        it('votes commit', async function() {
            let comm1 = await this.helper.getCommitHash(0, toWei(100), 1);
            let comm2 = await this.helper.getCommitHash(1, toWei(183), 2);
            let comm3 = await this.helper.getCommitHash(1, toWei(243), 3);

            let balanceBefore1 = await this.token.balanceOf(voters[0]);
            let balanceBefore2 = await this.token.balanceOf(voters[1]);
            let balanceBefore3 = await this.token.balanceOf(voters[2]);

            let fixedFee = await this.ranking.getFixedCommission(2);

            commissions[0] = commissions[0].add(fixedFee);
            commissions[1] = commissions[1].add(fixedFee);
            commissions[2] = commissions[2].add(fixedFee);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            await this.ranking.voteCommit(2, comm2, {from: voters[1]});
            await this.ranking.voteCommit(2, comm3, {from: voters[2]});
            startTime = await latestTime();

            await this.token.balanceOf(voters[0]).should.eventually.be.bignumber.equal(balanceBefore1.sub(fixedFee).toString());
            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(balanceBefore2.sub(fixedFee).toString());
            await this.token.balanceOf(voters[2]).should.eventually.be.bignumber.equal(balanceBefore3.sub(fixedFee).toString());
        });

        it('voting reveal', async function() {
            let balanceBefore1 = await this.token.balanceOf(voters[0]);
            let balanceBefore2 = await this.token.balanceOf(voters[1]);
            let balanceBefore3 = await this.token.balanceOf(voters[2]);

            let flexFee1 = await this.ranking.getDynamicCommission(1, toWei(100));
            let flexFee2 = await this.ranking.getDynamicCommission(2, toWei(183));
            let flexFee3 = await this.ranking.getDynamicCommission(3, toWei(243));

            commissions[0] = commissions[0].add(flexFee1);
            commissions[1] = commissions[1].add(flexFee2);
            commissions[2] = commissions[2].add(flexFee3);

            await increaseTimeTo(startTime + duration.seconds(181));

            await this.ranking.voteReveal(2, 0, toWei(100), 1, {from: voters[0]});
            await this.ranking.voteReveal(2, 1, toWei(183), 2, {from: voters[1]});
            await this.ranking.voteReveal(2, 1, toWei(243), 3, {from: voters[2]});

            let item = await this.ranking.getItem(2);

            await this.voting.getVoterStake(item[3], voters[0]).should.eventually.be.bignumber.equal(toWei(100));
            await this.voting.getVoterStake(item[3], voters[1]).should.eventually.be.bignumber.equal(toWei(183));
            await this.voting.getVoterStake(item[3], voters[2]).should.eventually.be.bignumber.equal(toWei(243));

            await this.token.balanceOf(voters[0]).should.eventually.be.bignumber.equal(balanceBefore1.sub(flexFee1).sub(toWei(100)).toString());
            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(balanceBefore2.sub(flexFee2).sub(toWei(183)).toString());
            await this.token.balanceOf(voters[2]).should.eventually.be.bignumber.equal(balanceBefore3.sub(flexFee3).sub(toWei(243)).toString());
        });


        it('finish voting', async function() {
            await increaseTimeTo(startTime + duration.seconds(361));

            let item = await this.ranking.getItem(2);
            console.log('VotingId:', item[3].toString());

            await this.ranking.finishVoting(2, {from: voters[0]});

            await this.voting.isWinner(item[3], voters[0]).should.eventually.be.equal(false);
            await this.voting.isWinner(item[3], voters[1]).should.eventually.be.equal(true);
            await this.voting.isWinner(item[3], voters[2]).should.eventually.be.equal(true);

            let voterInfo = await this.voting.getVoterInfo(item[3], voters[0]);
            console.log('voter 0 unstaked:', fromWei(voterInfo[3]));
            voterInfo[3].should.be.bignumber.equal(toWei(100));

            console.log('voter 0 commissions:', fromWei(commissions[0]));
            await this.token.balanceOf(voters[0]).should.eventually.be.bignumber.equal(new BigNumber(initialBalance).sub(commissions[0]).toString());

            console.log(voters[0], 'balance:', fromWei(await this.token.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.token.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.token.balanceOf(voters[2])));
        });

        it('unstake after 1s', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(1));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log(voters[0], 'balance:', fromWei(await this.token.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.token.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.token.balanceOf(voters[2])));
        });

        it('unstake after 5s', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(5));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log(voters[0], 'balance:', fromWei(await this.token.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.token.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.token.balanceOf(voters[2])));
        });

        it('unstake after 10s', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(10));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log(voters[0], 'balance:', fromWei(await this.token.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.token.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.token.balanceOf(voters[2])));
        });

        it('unstake full', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(1000));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log('Item 2 rank:', fromWei(await this.ranking.getCurrentRank(2)));

            console.log(voters[0], 'balance:', fromWei(await this.token.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.token.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.token.balanceOf(voters[2])));
        });
    });

    describe('commissions', function () {
        before(async function() {
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);

            await this.ranking.newItem(1, defaultRanks[0], accounts[0]);
            await this.ranking.newItem(2, defaultRanks[1], accounts[0]);
            await this.ranking.newItem(3, defaultRanks[2], accounts[0]);
        });

        it('fixed commissions', async function () {
            let rank1 = await this.ranking.getCurrentRank(1);
            let rank2 = await this.ranking.getCurrentRank(2);
            let rank3 = await this.ranking.getCurrentRank(3);
            let avgStake = await this.ranking.avgStake();
            let maxRank = await this.ranking.maxRank();
            console.log('avg stake:', fromWei(avgStake));
            console.log('max rank:', fromWei(maxRank));
            console.log(`item 1 with rank ${fromWei(rank1)}, fixed commission:`, fromWei(await this.ranking.getFixedCommission(1)));
            console.log(`item 2 with rank ${fromWei(rank2)}, fixed commission:`, fromWei(await this.ranking.getFixedCommission(2)));
            console.log(`item 3 with rank ${fromWei(rank3)}, fixed commission:`, fromWei(await this.ranking.getFixedCommission(3)));
        });

        it('flex commissions', async function () {
            let avgStake = await this.ranking.avgStake();
            console.log('avg stake:', fromWei(avgStake));
            console.log('for 100 tokens', fromWei(await this.ranking.getDynamicCommission(1, toWei(100))));
            console.log('for 200 tokens', fromWei(await this.ranking.getDynamicCommission(1, toWei(200))));
            console.log('for 300 tokens', fromWei(await this.ranking.getDynamicCommission(1, toWei(300))));
            console.log('for 350 tokens', fromWei(await this.ranking.getDynamicCommission(1, toWei(350))));
        });
    });

    describe('finish if 1 commits & 0 reveals', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);

            await this.ranking.newItem(1, defaultRanks[0], accounts[0]);
            await this.ranking.newItem(2, defaultRanks[1], accounts[0]);
            await this.ranking.newItem(3, defaultRanks[2], accounts[0]);
        });

        it('commit', async function () {
            let comm = await this.helper.getCommitHash(0, toWei(100), 1);

            await this.ranking.voteCommit(2, comm, {from: voters[0]});
            commitTime = await latestTime();
        });

        it('finish', async function () {
            await increaseTimeTo(commitTime + duration.seconds(361));
            await this.ranking.finishVoting(2, {from: voters[0]});
        });
    });

    describe('finish if 2 commits & 1 reveals', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);

            await this.ranking.newItem(1, defaultRanks[0], accounts[0]);
            await this.ranking.newItem(2, defaultRanks[1], accounts[0]);
            await this.ranking.newItem(3, defaultRanks[2], accounts[0]);
        });

        it('2 commits', async function () {
            let comm1 = await this.helper.getCommitHash(0, toWei(100), 1);
            let comm2 = await this.helper.getCommitHash(1, toWei(183), 2);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            await this.ranking.voteCommit(2, comm2, {from: voters[1]});
            commitTime = await latestTime();
        });

        it('1 reveal', async function () {
            await increaseTimeTo(commitTime + duration.seconds(181));
            await this.ranking.voteReveal(2, 0, toWei(100), 1, {from: voters[0]});
        });

        it('finish', async function () {
            await increaseTimeTo(commitTime + duration.seconds(361));
            await this.ranking.finishVoting(2, {from: voters[0]});
        });
    });


    describe('under zero vote', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);

            await this.ranking.newItem(1, defaultRanks[0], accounts[0]);
            await this.ranking.newItem(2, defaultRanks[1], accounts[0]);
            await this.ranking.newItem(3, defaultRanks[2], accounts[0]);
        });

        it('commits', async function () {
            let comm1 = await this.helper.getCommitHash(1, toWei(100), 1);
            let comm2 = await this.helper.getCommitHash(0, toWei(383), 2);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            await this.ranking.voteCommit(2, comm2, {from: voters[1]});
            commitTime = await latestTime();
        });

        it('reveals', async function () {
            await increaseTimeTo(commitTime + duration.seconds(181));
            await this.ranking.voteReveal(2, 1, toWei(100), 1, {from: voters[0]});
            await this.ranking.voteReveal(2, 0, toWei(383), 2, {from: voters[1]});
        });

        it('finish', async function () {
            await increaseTimeTo(commitTime + duration.seconds(361));
            await this.ranking.finishVoting(2, {from: voters[0]});

            let finishTime = await latestTime();
            await increaseTimeTo(finishTime + duration.seconds(5));
            console.log('Item rank after 5s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(7));
            console.log('Item rank after 7s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(20));
            console.log('Item rank after 20s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(1000));
            let rank = await this.ranking.getCurrentRank(2);
            console.log('Item rank after 1000s:', fromWei(rank));
            rank.should.be.bignumber.equal(0);
        });
    });


    describe('under zero vote when already exist down moving (not to 0)', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);

            await this.ranking.newItem(1, toWei(90), accounts[0]);
            await this.ranking.newItem(2, toWei(1000), accounts[0]);
            await this.ranking.newItem(3, toWei(30), accounts[0]);

            let comm1 = await this.helper.getCommitHash(0, toWei(500), 1);
            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            await increaseTimeTo(await latestTime() + duration.seconds(181));
            await this.ranking.voteReveal(2, 0, toWei(500), 1, {from: voters[0]});
            await increaseTimeTo(await latestTime() + duration.seconds(181));
            await this.ranking.finishVoting(2, {from: voters[0]});
        });

        it('commits', async function () {
            let comm1 = await this.helper.getCommitHash(0, toWei(200), 1);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            commitTime = await latestTime();
        });

        it('reveals', async function () {
            await increaseTimeTo(commitTime + duration.seconds(181));
            await this.ranking.voteReveal(2, 0, toWei(200), 1, {from: voters[0]});
        });

        it('finish', async function () {
            await increaseTimeTo(commitTime + duration.seconds(361));
            await this.ranking.finishVoting(2, {from: voters[0]});

            let finishTime = await latestTime();
            await increaseTimeTo(finishTime + duration.seconds(150));
            console.log('Item rank after 150s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(300));
            console.log('Item rank after 300s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(2000));
            let rank = await this.ranking.getCurrentRank(2);
            console.log('Item rank after 2000s:', fromWei(rank));
            rank.should.be.bignumber.not.equal(0);
        });
    });


    describe('under zero vote when already exist down moving (to 0)', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);

            await this.ranking.newItem(1, toWei(90), accounts[0]);
            await this.ranking.newItem(2, toWei(1000), accounts[0]);
            await this.ranking.newItem(3, toWei(30), accounts[0]);

            let comm1 = await this.helper.getCommitHash(0, toWei(600), 1);
            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            await increaseTimeTo(await latestTime() + duration.seconds(181));
            await this.ranking.voteReveal(2, 0, toWei(600), 1, {from: voters[0]});
            await increaseTimeTo(await latestTime() + duration.seconds(181));
            await this.ranking.finishVoting(2, {from: voters[0]});
        });

        it('commits', async function () {
            let comm1 = await this.helper.getCommitHash(0, toWei(500), 1);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            commitTime = await latestTime();
        });

        it('reveals', async function () {
            await increaseTimeTo(commitTime + duration.seconds(181));
            await this.ranking.voteReveal(2, 0, toWei(500), 1, {from: voters[0]});
        });

        it('finish', async function () {
            await increaseTimeTo(commitTime + duration.seconds(361));
            await this.ranking.finishVoting(2, {from: voters[0]});

            let finishTime = await latestTime();
            await increaseTimeTo(finishTime + duration.seconds(150));
            console.log('Item rank after 150s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(300));
            console.log('Item rank after 300s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(2000));
            let rank = await this.ranking.getCurrentRank(2);
            console.log('Item rank after 2000s:', fromWei(rank));
            rank.should.be.bignumber.equal(0);
        });
    });


    describe('remove (without movings)', function () {
        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            await this.token.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, accounts[0], voters[3], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);
        });

        it('add', async function () {
            await this.ranking.newItem(1, toWei(90), voters[0]);
            await this.ranking.newItem(2, toWei(50), voters[1]);
            await this.ranking.newItem(3, toWei(70), voters[2]);

            (await this.ranking.getItemsWithRank())[0].length.should.be.equal(3);
        });

        it('remove', async function () {
            await this.ranking.removeItem(2);

            await expectThrow(this.ranking.getItem(2));
            (await this.ranking.getItemsWithRank())[0].length.should.be.equal(2);
        });
    });


    describe('remove (with movings)', function () {
        before(async function() {
            await advanceBlock();
            this.token = await Token.new();
            this.admin = await Admin.new();
            this.helper = await Helper.new();
            this.voting = await Voting.new(this.admin.address);
            this.ranking = await Ranking.new(this.admin.address);

            await this.token.transfer(voters[0], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[0]});
            await this.token.transfer(voters[1], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[1]});
            await this.token.transfer(voters[2], initialBalance);
            await this.token.approve(this.ranking.address, initialBalance, {from: voters[2]});

            this.voterBalance = await this.token.balanceOf(voters[0]);

            await this.ranking.init(this.voting.address, accounts[0], voters[3], this.token.address, ...rankingParams);
            await this.voting.init(this.ranking.address, ...votingParams);

            await this.ranking.newItem(1, toWei(90), voters[0]);
            await this.ranking.newItem(2, toWei(50), voters[1]);
            await this.ranking.newItem(3, toWei(70), voters[2]);
        });

        it('voting', async function () {
            let comm1 = await this.helper.getCommitHash(0, toWei(500), 1);

            let comm = await this.ranking.getFixedCommission(2);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            let commitTime = await latestTime();

            comm.add(await this.ranking.getDynamicCommission(2, toWei(100)));

            await increaseTimeTo(commitTime + duration.seconds(181));
            await this.ranking.voteReveal(2, 0, toWei(500), 1, {from: voters[0]});

            await increaseTimeTo(commitTime + duration.seconds(361));
            await this.ranking.finishVoting(2, {from: voters[0]});
        });

        it('remove', async function () {
            await this.ranking.removeItem(2);

            await expectThrow(this.ranking.getItem(2));
            (await this.ranking.getItemsWithRank())[0].length.should.be.equal(2);

            await this.token.balanceOf(voters[0]).should.eventually.be.bignumber.equal(this.voterBalance);
        });
    })
});
