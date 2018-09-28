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


const Voting = artifacts.require('Voting');
const Ranking = artifacts.require('Ranking');
const Helper = artifacts.require('Helper');
const Admin = artifacts.require('Admin');

const fromWei = (num) => {
    if (typeof num === 'string' || typeof num === 'number')
        return web3.fromWei(num);
    return web3.fromWei(num.toString());
};

async function beforeFunc() {
    await advanceBlock();
    this.voting = await Voting.new();
    this.helper = await Helper.new();
    this.admin = await Admin.new();
    this.ranking = await Ranking.new(this.admin.address);

    await this.ranking.transfer(voters[0], initialBalance);
    await this.ranking.transfer(voters[1], initialBalance);
    await this.ranking.transfer(voters[2], initialBalance);

    await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

    await this.ranking.init(this.voting.address, ...rankingParams);
}

contract('Ranking', function(accounts) {

    let voters = accounts.slice(2, 5);
    let initialBalance = toWei(10000);
    let rankingParams = [ 1, 100, 100, 1, 10, toWei(0.5), 180, 180, toWei(300) ];

    describe('full', function() {
        before(async function() {
            await advanceBlock();
            this.voting = await Voting.new();
            this.helper = await Helper.new();
            this.admin = await Admin.new();
            this.ranking = await Ranking.new(this.admin.address);

            await this.ranking.transfer(voters[0], initialBalance);
            await this.ranking.transfer(voters[1], initialBalance);
            await this.ranking.transfer(voters[2], initialBalance);

            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, ...rankingParams);
        });

        let startTime = null;

        it('add items', async function() {
            await this.ranking.newItemsWithRanks([1, 2, 3], [toWei(90), toWei(50), toWei(30)]);

            (await this.ranking.getItemsWithRank.call())[0].length.should.be.equal(3);
            (await this.ranking.getItemsWithRank.call())[1].length.should.be.equal(3);
        });

        it('votes commit', async function() {
            let comm1 = await this.helper.getCommitHash(0, toWei(100), 1);
            let comm2 = await this.helper.getCommitHash(1, toWei(183), 2);
            let comm3 = await this.helper.getCommitHash(1, toWei(243), 3);

            let balanceBefore1 = await this.ranking.balanceOf(voters[0]);
            let balanceBefore2 = await this.ranking.balanceOf(voters[1]);
            let balanceBefore3 = await this.ranking.balanceOf(voters[2]);

            let fixedFee1 = await this.ranking.getFixedCommission(1);
            let fixedFee2 = await this.ranking.getFixedCommission(2);
            let fixedFee3 = await this.ranking.getFixedCommission(3);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            await this.ranking.voteCommit(2, comm2, {from: voters[1]});
            await this.ranking.voteCommit(2, comm3, {from: voters[2]});
            startTime = await latestTime();

            await this.ranking.balanceOf(voters[0]).should.eventually.be.bignumber.equal(balanceBefore1.sub(fixedFee1).toString());
            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(balanceBefore2.sub(fixedFee2).toString());
            await this.ranking.balanceOf(voters[2]).should.eventually.be.bignumber.equal(balanceBefore3.sub(fixedFee3).toString());
        });

        it('voting reveal', async function() {
            let balanceBefore1 = await this.ranking.balanceOf(voters[0]);
            let balanceBefore2 = await this.ranking.balanceOf(voters[1]);
            let balanceBefore3 = await this.ranking.balanceOf(voters[2]);

            let item = await this.ranking.getItem.call(2);
            let voting = await this.ranking.getVoting.call(item[3]);
            let avgStake = voting[6];

            let flexFee1 = await this.ranking.getDynamicCommission(toWei(100), avgStake);
            let flexFee2 = await this.ranking.getDynamicCommission(toWei(183), avgStake);
            let flexFee3 = await this.ranking.getDynamicCommission(toWei(243), avgStake);

            await increaseTimeTo(startTime + duration.seconds(181));

            await this.ranking.voteReveal(2, 0, toWei(100), 1, {from: voters[0]});
            await this.ranking.voteReveal(2, 1, toWei(183), 2, {from: voters[1]});
            await this.ranking.voteReveal(2, 1, toWei(243), 3, {from: voters[2]});

            await this.ranking.balanceOf(voters[0]).should.eventually.be.bignumber.equal(balanceBefore1.sub(flexFee1).sub(toWei(100)).toString());
            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(balanceBefore2.sub(flexFee2).sub(toWei(183)).toString());
            await this.ranking.balanceOf(voters[2]).should.eventually.be.bignumber.equal(balanceBefore3.sub(flexFee3).sub(toWei(243)).toString());
        });


        it('finish voting', async function() {
            await increaseTimeTo(startTime + duration.seconds(361));

            await this.ranking.finishVoting(2, {from: voters[0]});

            let item = await this.ranking.getItem.call(2);

            console.log('Item 2:', item);

            let moving = await this.ranking.getMoving.call(item[4][0]);

            console.log('Moving:', moving);

            let voting = await this.ranking.getVoting.call(moving[4]);

            console.log('Voting:', voting);

            for (let i = 0; i < voting[5].length; ++i) {
                let voterInfo = await this.ranking.getVoterInfo.call(moving[4], voting[5][i]);

                console.log('Info for ', voting[5][i], ': ', voterInfo);
            }

            console.log(voters[0], 'balance:', fromWei(await this.ranking.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.ranking.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.ranking.balanceOf(voters[2])));
        });

        it('unstake after 1s', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(1));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log(voters[0], 'balance:', fromWei(await this.ranking.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.ranking.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.ranking.balanceOf(voters[2])));
        });

        it('unstake after 5s', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(5));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log(voters[0], 'balance:', fromWei(await this.ranking.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.ranking.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.ranking.balanceOf(voters[2])));
        });

        it('unstake after 10s', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(10));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log(voters[0], 'balance:', fromWei(await this.ranking.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.ranking.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.ranking.balanceOf(voters[2])));
        });

        it('unstake full', async function() {
            await increaseTimeTo(await latestTime() + duration.seconds(1000));

            await this.ranking.unstake(2, {from: voters[0]});
            await this.ranking.unstake(2, {from: voters[1]});
            await this.ranking.unstake(2, {from: voters[2]});

            console.log('Item 2 rank:', fromWei(await this.ranking.getCurrentRank(2)));

            console.log(voters[0], 'balance:', fromWei(await this.ranking.balanceOf(voters[0])));
            console.log(voters[1], 'balance:', fromWei(await this.ranking.balanceOf(voters[1])));
            console.log(voters[2], 'balance:', fromWei(await this.ranking.balanceOf(voters[2])));
        });
    });

    describe('flex fee', function () {
        before(async function() {
            await advanceBlock();
            this.voting = await Voting.new();
            this.helper = await Helper.new();
            this.admin = await Admin.new();
            this.ranking = await Ranking.new(this.admin.address);

            await this.ranking.transfer(voters[0], initialBalance);
            await this.ranking.transfer(voters[1], initialBalance);
            await this.ranking.transfer(voters[2], initialBalance);

            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, ...rankingParams);

            await this.ranking.newItemsWithRanks([1, 2, 3], [toWei(90), toWei(50), toWei(30)]);
        });

        it('fixed commissions', async function () {
            console.log('item 1', await this.ranking.getFixedCommission(1));
            console.log('item 2', await this.ranking.getFixedCommission(2));
            console.log('item 3', await this.ranking.getFixedCommission(3));
        });

        it('flex commissions', async function () {
            let avgStake = await this.ranking.avgStake();

            console.log('for 100 tokens', await this.ranking.getDynamicCommission(toWei(100), avgStake));
            console.log('for 150 tokens', await this.ranking.getDynamicCommission(toWei(150), avgStake));
            console.log('for 200 tokens', await this.ranking.getDynamicCommission(toWei(200), avgStake));
            console.log('for 250 tokens', await this.ranking.getDynamicCommission(toWei(250), avgStake));
        });
    });

    describe('finish if 1 commits & 0 reveals', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.voting = await Voting.new();
            this.helper = await Helper.new();
            this.admin = await Admin.new();
            this.ranking = await Ranking.new(this.admin.address);

            await this.ranking.transfer(voters[0], initialBalance);
            await this.ranking.transfer(voters[1], initialBalance);
            await this.ranking.transfer(voters[2], initialBalance);

            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, ...rankingParams);

            await this.ranking.newItemsWithRanks([1, 2, 3], [toWei(90), toWei(50), toWei(30)]);
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
            this.voting = await Voting.new();
            this.helper = await Helper.new();
            this.admin = await Admin.new();
            this.ranking = await Ranking.new(this.admin.address);

            await this.ranking.transfer(voters[0], initialBalance);
            await this.ranking.transfer(voters[1], initialBalance);
            await this.ranking.transfer(voters[2], initialBalance);

            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, ...rankingParams);

            await this.ranking.newItemsWithRanks([1, 2, 3], [toWei(90), toWei(50), toWei(30)]);
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
            this.voting = await Voting.new();
            this.helper = await Helper.new();
            this.admin = await Admin.new();
            this.ranking = await Ranking.new(this.admin.address);

            await this.ranking.transfer(voters[0], initialBalance);
            await this.ranking.transfer(voters[1], initialBalance);
            await this.ranking.transfer(voters[2], initialBalance);

            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, ...rankingParams);

            await this.ranking.newItemsWithRanks([1, 2, 3], [toWei(90), toWei(53), toWei(30)]);
        });

        it('commits', async function () {
            let comm1 = await this.helper.getCommitHash(1, toWei(100), 1);
            let comm2 = await this.helper.getCommitHash(0, toWei(183), 2);

            await this.ranking.voteCommit(2, comm1, {from: voters[0]});
            await this.ranking.voteCommit(2, comm2, {from: voters[1]});
            commitTime = await latestTime();
        });

        it('reveals', async function () {
            await increaseTimeTo(commitTime + duration.seconds(181));
            await this.ranking.voteReveal(2, 1, toWei(100), 1, {from: voters[0]});
            await this.ranking.voteReveal(2, 0, toWei(183), 2, {from: voters[1]});
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
        });
    });


    describe('under zero vote when already exist down moving (not to 0)', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.voting = await Voting.new();
            this.helper = await Helper.new();
            this.admin = await Admin.new();
            this.ranking = await Ranking.new(this.admin.address);

            await this.ranking.transfer(voters[0], initialBalance);
            await this.ranking.transfer(voters[1], initialBalance);
            await this.ranking.transfer(voters[2], initialBalance);

            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, ...rankingParams);

            await this.ranking.newItemsWithRanks([1, 2, 3], [toWei(90), toWei(1000), toWei(30)]);

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

            await increaseTimeTo(finishTime + duration.seconds(450));
            console.log('Item rank after 450s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(2000));
            console.log('Item rank after 2000s:', fromWei(await this.ranking.getCurrentRank(2)));
        });
    });


    describe('under zero vote when already exist down moving (to 0)', function () {
        let commitTime = null;

        before(async function() {
            await advanceBlock();
            this.voting = await Voting.new();
            this.helper = await Helper.new();
            this.admin = await Admin.new();
            this.ranking = await Ranking.new(this.admin.address);

            await this.ranking.transfer(voters[0], initialBalance);
            await this.ranking.transfer(voters[1], initialBalance);
            await this.ranking.transfer(voters[2], initialBalance);

            await this.ranking.balanceOf(voters[1]).should.eventually.be.bignumber.equal(initialBalance);

            await this.ranking.init(this.voting.address, ...rankingParams);

            await this.ranking.newItemsWithRanks([1, 2, 3], [toWei(90), toWei(1000), toWei(30)]);

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

            await increaseTimeTo(finishTime + duration.seconds(450));
            console.log('Item rank after 450s:', fromWei(await this.ranking.getCurrentRank(2)));

            await increaseTimeTo(finishTime + duration.seconds(2000));
            console.log('Item rank after 2000s:', fromWei(await this.ranking.getCurrentRank(2)));
        });
    });
});
