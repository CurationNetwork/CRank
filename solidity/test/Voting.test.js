const { latestTime } = require('../node_modules/zeppelin-solidity/test/helpers/latestTime');
const { increaseTimeTo, duration } = require('../node_modules/zeppelin-solidity/test/helpers/increaseTime');
const { advanceBlock } = require('../node_modules/zeppelin-solidity/test/helpers/advanceToBlock');
const { expectThrow } = require('../node_modules/zeppelin-solidity/test/helpers/expectThrow');
const { EVMRevert } = require('../node_modules/zeppelin-solidity/test/helpers/EVMRevert');


const abi = require('ethereumjs-abi');
const BigNumber = web3.BigNumber;
const chai =require('chai');
chai.use(require('chai-bignumber')(BigNumber));
chai.use(require('chai-as-promised')); // Order is important
chai.should();

const Voting = artifacts.require('Voting');

const utils = {
    createVoteHash: (vote, stake, salt) => {
        return `0x${abi.soliditySHA3(['uint', 'uint', 'uint'], [vote, stake, salt]).toString('hex')}`;
    },
};


contract('Voting', function(accounts) {
    before(async function(){
        await advanceBlock();

        this.voting = await Voting.new();
        await this.voting.init();
    });

    describe('happy path vote', function() {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: 1000,
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }, {
            direction: 1,
            stake: 500,
            salt: Math.random() * 1000 | 0,
            voter: accounts[3]
        }];

        let startTime = null;
        let pollId = null;

        it('start poll', async function() {
            pollId = await this.voting.startPoll.call(itemId, commitTtl, revealTtl);
            await this.voting.startPoll(0, 180, 180);
            startTime = await latestTime();
        });

        it('exists check', async function () {
            await this.voting.pollExists(pollId).should.eventually.be.equal(true);
        });

        it('commits', async function () {
            let hash1 = utils.createVoteHash(votes[0].direction, votes[0].stake, votes[0].salt);
            let hash2 = utils.createVoteHash(votes[1].direction, votes[1].stake, votes[1].salt);

            await this.voting.commitVote(pollId, hash1, votes[0].voter);
            await this.voting.commitVote(pollId, hash2, votes[1].voter);
        });

        it('reveals', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + 1));

            await this.voting.revealVote(pollId, votes[0].direction, votes[0].stake, votes[0].salt, votes[0].voter);
            await this.voting.revealVote(pollId, votes[1].direction, votes[1].stake, votes[1].salt, votes[1].voter);
        });

        it('results', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + revealTtl + 1));

            await this.voting.result.call(pollId).should.eventually.be.bignumber.equal(0);

            await this.voting.getOverallStake.call(pollId).should.eventually.be.bignumber.equal(votes[0].stake + votes[1].stake);

            let result = await this.voting.getPollResult.call(pollId);
            result[0].toString().should.be.equal('500');
            result[1].toString().should.be.equal('1000');

            await this.voting.isWinner.call(pollId, votes[0].voter).should.eventually.be.equal(true);
            await this.voting.isWinner.call(pollId, votes[1].voter).should.eventually.be.equal(false);
        });
    });

    describe('commit after ttl', function () {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: 1000,
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }, {
            direction: 1,
            stake: 500,
            salt: Math.random() * 1000 | 0,
            voter: accounts[3]
        }];

        let startTime = null;
        let pollId = null;

        it('start poll', async function() {
            pollId = await this.voting.startPoll.call(itemId, commitTtl, revealTtl);
            await this.voting.startPoll(0, 180, 180);
            startTime = await latestTime();
        });

        it('commit', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + 1));
            let hash1 = utils.createVoteHash(votes[0].direction, votes[0].stake, votes[0].salt);

            await expectThrow(this.voting.commitVote(pollId, hash1, votes[0].voter));
        });
    });

    describe('reveal after ttl', function () {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: 1000,
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }, {
            direction: 1,
            stake: 500,
            salt: Math.random() * 1000 | 0,
            voter: accounts[3]
        }];

        let startTime = null;
        let pollId = null;

        it('start poll', async function() {
            pollId = await this.voting.startPoll.call(itemId, commitTtl, revealTtl);
            await this.voting.startPoll(0, 180, 180);
            startTime = await latestTime();
        });

        it('commit', async function () {
            let hash1 = utils.createVoteHash(votes[0].direction, votes[0].stake, votes[0].salt);

            await this.voting.commitVote(pollId, hash1, votes[0].voter);
        });

        it('reveal', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + revealTtl + 1));

            await expectThrow(this.voting.revealVote(pollId, votes[0].direction, votes[0].stake, votes[0].salt, votes[0].voter));
        });
    });

    describe('result before finish', function () {
        let commitTtl = 180;
        let revealTtl = 180;
        let itemId = 0;
        let votes = [{
            direction: 0,
            stake: 1000,
            salt: Math.random() * 1000 | 0,
            voter: accounts[2]
        }, {
            direction: 1,
            stake: 500,
            salt: Math.random() * 1000 | 0,
            voter: accounts[3]
        }];

        let startTime = null;
        let pollId = null;

        it('start poll', async function() {
            pollId = await this.voting.startPoll.call(itemId, commitTtl, revealTtl);
            await this.voting.startPoll(0, 180, 180);
            startTime = await latestTime();
        });

        it('results during commit', async function () {
            await expectThrow(this.voting.result.call(pollId));
        });

        it('results during reveal', async function () {
            await increaseTimeTo(startTime + duration.seconds(commitTtl + 1));
            await expectThrow(this.voting.result.call(pollId));
        });
    });
});