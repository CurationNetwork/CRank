const { latestTime } = require('../node_modules/zeppelin-solidity/test/helpers/latestTime');
const { increaseTimeTo, duration } = require('../node_modules/zeppelin-solidity/test/helpers/increaseTime');
const { advanceBlock } = require('../node_modules/zeppelin-solidity/test/helpers/advanceToBlock');
const { expectThrow } = require('../node_modules/zeppelin-solidity/test/helpers/expectThrow');
const { EVMRevert } = require('../node_modules/zeppelin-solidity/test/helpers/EVMRevert');


const toWei = web3.toWei;
const fromWei = web3.fromWei;
const abi = require('ethereumjs-abi');
const BigNumber = web3.BigNumber;
const chai =require('chai');
chai.use(require('chai-bignumber')(BigNumber));
chai.use(require('chai-as-promised')); // Order is important
chai.should();

const Voting = artifacts.require('Voting');
const Admin = artifacts.require('Admin');

const utils = {
    createVoteHash: (vote, stake, salt) => {
        return `0x${abi.soliditySHA3(['uint', 'uint', 'uint'], [vote, stake, salt]).toString('hex')}`;
    },
};


contract('Voting', function(accounts) {

    // dynamicFeeLinearRate, dynamicFeeLinearPrecision, maxOverStakeFactor, maxFixedFeeRate, maxFixedFeePrecision,
    let votingParams = [1, 100, 100, 5, 100];

    before(async function(){
        await advanceBlock();

        this.admin = await Admin.new();
        this.voting = await Voting.new(this.admin.address);

        await this.voting.init(accounts[0], ...votingParams);
    });

    describe('happy path vote', function() {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: toWei(50),
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }, {
            direction: 1,
            stake: toWei(100),
            salt: Math.random() * 1000 | 0,
            voter: accounts[3]
        }];

        let startTime = null;
        let votingId = null;
        let movingSpeed = toWei(0.05);
        let avgStake = toWei(100);
        let maxRank = toWei(800);
        let itemRank = toWei(600);
        let totalSupply = toWei(1000000);
        let itemBounty = 0;

        it('start voting', async function() {
            votingId = await this.voting.startVoting.call(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            await this.voting.startVoting(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            startTime = await latestTime();
        });

        it('commits', async function () {
            let hash1 = utils.createVoteHash(votes[0].direction, votes[0].stake, votes[0].salt);
            let hash2 = utils.createVoteHash(votes[1].direction, votes[1].stake, votes[1].salt);

            await this.voting.commitVote(votingId, hash1, votes[0].voter);
            await this.voting.commitVote(votingId, hash2, votes[1].voter);
        });

        it('get voters', async function () {
            let voters = await this.voting.getVoters(votingId);

            voters.find(v => v === votes[0].voter).should.be.not.equal(null);
            voters.find(v => v === votes[1].voter).should.be.not.equal(null);
        });

        it('reveals', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + 1));

            await this.voting.revealVote(votingId, votes[0].direction, votes[0].stake, votes[0].salt, votes[0].voter, totalSupply);
            await this.voting.revealVote(votingId, votes[1].direction, votes[1].stake, votes[1].salt, votes[1].voter, totalSupply);
        });

        it('finish', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + revealTtl + 1));

            let result = await this.voting.finishVoting.call(votingId);
            await this.voting.finishVoting(votingId);

            result[0].toNumber().should.be.equal(1);
            result[1].toString().should.be.equal(toWei(50));
            result[2].toString().should.be.equal(toWei(0.05));
        });

        it('unstakeAll', async function () {
            await this.voting.unstakeAll.call(votingId, votes[0].voter).should.eventually.be.bignumber.equal(votes[0].stake.toString());
            await this.voting.unstakeAll.call(votingId, votes[1].voter).should.eventually.be.bignumber.equal(votes[1].stake.toString());
        });
    });

    describe('commit after ttl', function() {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: toWei(50),
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }];

        let startTime = null;
        let votingId = null;
        let movingSpeed = toWei(0.05);
        let avgStake = toWei(100);
        let maxRank = toWei(800);
        let itemRank = toWei(600);
        let itemBounty = 0;

        it('start voting', async function() {
            votingId = await this.voting.startVoting.call(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            await this.voting.startVoting(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            startTime = await latestTime();
        });

        it('commit', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + 1));
            let hash1 = utils.createVoteHash(votes[0].direction, votes[0].stake, votes[0].salt);

            await expectThrow(this.voting.commitVote(votingId, hash1, votes[0].voter));
        });
    });

    describe('reveal after ttl', function () {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: toWei(50),
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }];

        let startTime = null;
        let votingId = null;
        let movingSpeed = toWei(0.05);
        let avgStake = toWei(100);
        let maxRank = toWei(800);
        let itemRank = toWei(600);
        let totalSupply = toWei(1000000);
        let itemBounty = 0;

        it('start voting', async function() {
            votingId = await this.voting.startVoting.call(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            await this.voting.startVoting(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            startTime = await latestTime();
        });

        it('commit', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + 1));
            let hash1 = utils.createVoteHash(votes[0].direction, votes[0].stake, votes[0].salt);

            await expectThrow(this.voting.commitVote(votingId, hash1, votes[0].voter));
        });

        it('reveal', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + revealTtl + 1));

            await expectThrow(this.voting.revealVote(votingId, votes[0].direction, votes[0].stake, votes[0].salt, votes[0].voter, totalSupply));
        });
    });

    describe('result before finish', function () {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: toWei(50),
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }];

        let startTime = null;
        let votingId = null;
        let movingSpeed = toWei(0.05);
        let avgStake = toWei(100);
        let maxRank = toWei(800);
        let itemRank = toWei(600);
        let totalSupply = toWei(1000000);
        let itemBounty = 0;

        it('start voting', async function() {
            votingId = await this.voting.startVoting.call(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            await this.voting.startVoting(itemId, itemBounty, commitTtl, revealTtl, movingSpeed, avgStake, maxRank, itemRank);
            startTime = await latestTime();
        });

        it('commit', async function () {
            let hash1 = utils.createVoteHash(votes[0].direction, votes[0].stake, votes[0].salt);

            this.voting.commitVote(votingId, hash1, votes[0].voter);
        });

        it('reveal', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + 1));

            this.voting.revealVote(votingId, votes[0].direction, votes[0].stake, votes[0].salt, votes[0].voter, totalSupply);
        });

        it('finish', async function () {
            await expectThrow(this.voting.finishVoting(votingId));
        });
    });
});