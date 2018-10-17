pragma solidity ^0.4.24;
import "zeppelin-solidity/contracts/math/SafeMath.sol";
import './Helper.sol';
import "./Admin.sol";
import "./Ranking.sol";


contract Voting {

    using SafeMath for uint;


    // ============
    // EVENTS:
    // ============

    event VoteCommitted(
        uint indexed itemId,
        uint indexed votingId,
        address indexed voter
    );

    event VoteRevealed(
        uint indexed itemId,
        uint indexed votingId,
        address indexed voter,
        uint direction,
        uint stake,
        uint salt
    );

    event VotingCreated(
        uint indexed itemId,
        uint indexed votingId,
        uint commitEndTime,
        uint revealEndTime
    );

    event VotingFinished(
        uint indexed itemId,
        uint indexed votingId,
        uint votesUp,
        uint votesDown
    );


    // ============
    // DATA STRUCTURES:
    // ============

    mapping(uint => Voting) public votingMap;

    enum VotingState { Commiting, Revealing, Finished, Calculated }

    struct VoterInfo {
        bytes32 commitment;
        uint direction;
        uint stake;
        uint unstaked;
        uint reward;
        bool rewardClaimed;
    }

    struct Voting {
        uint itemId;
        uint fixedFee;
        uint movingSpeed;
        uint avgStake;
        uint commitEndTime;
        uint revealEndTime;
        uint totalPrize;

        uint votesUp;
        uint votesDown;

        bool calculated;

        address[] votersAddresses;
        mapping (address => VoterInfo) voters;
    }


    // ============
    // STATE VARIABLES
    // ============

    Admin accessContract;

    uint constant public INITIAL_VOTING_NONCE = 0;
    uint public votingNonce;
    address public rankingContractAddress;

    uint public dynamicFeeLinearRate;
    uint public dynamicFeeLinearPrecision;
    uint public maxOverStakeFactor;

    uint public maxFixedFeeRate;
    uint public maxFixedFeePrecision;


    constructor(address _accessContractAddress)
        public
    {
        votingNonce = INITIAL_VOTING_NONCE;
        accessContract = Admin(_accessContractAddress);
    }

    function init(address _rankingContractAddress, uint dynamicFeeLinearRate_, uint dynamicFeeLinearPrecision_,
                uint maxOverStakeFactor_, uint maxFixedFeeRate_, uint maxFixedFeePrecision_
    )
        public
        onlyOwner
    {
        dynamicFeeLinearRate = dynamicFeeLinearRate_;
        dynamicFeeLinearPrecision = dynamicFeeLinearPrecision_;
        maxOverStakeFactor = maxOverStakeFactor_;

        maxFixedFeeRate = maxFixedFeeRate_;
        maxFixedFeePrecision = maxFixedFeePrecision_;

        rankingContractAddress = _rankingContractAddress;
    }


    // =========
    // MODIFIERS
    // =========

    modifier onlyOwner {
        require(accessContract.isOwner(msg.sender));
        _;
    }

    modifier onlySuperuser {
        require(accessContract.isSuperuser(msg.sender));
        _;
    }

    modifier onlyForRanking() {
        require(msg.sender == rankingContractAddress);
        _;
    }

    modifier onlyVotingExists(uint _votingId) {
        require(votingMap[_votingId].commitEndTime != 0);
        _;
    }

    modifier onlyWhenCommit(uint _votingId) {
        require(votingMap[_votingId].commitEndTime >= now);
        _;
    }

    modifier onlyWhenReveal(uint _votingId) {
        require(votingMap[_votingId].commitEndTime < now);
        require(votingMap[_votingId].revealEndTime >= now);
        _;
    }

    modifier onlyWhenFinished(uint _votingId) {
        require(votingMap[_votingId].revealEndTime < now);
        _;
    }

    modifier onlyWhenCalculated(uint _votingId) {
        require(votingMap[_votingId].calculated, "not calculated");
        _;
    }


    // =================
    // VIEW METHODS
    // =================

    function getFixedCommission(uint _avgStake, uint _maxRank, uint _itemRank)
        public
        view
        returns (uint)
    {
        return Helper.calculateFixedCommission(maxFixedFeeRate, maxFixedFeePrecision, _avgStake, _maxRank, _itemRank);
    }

    function getDynamicCommission(uint _avgStake, uint _totalSupply, uint _stake)
        public
        view
        returns (uint)
    {
        return Helper.calculateDynamicCommission(dynamicFeeLinearRate, dynamicFeeLinearPrecision, maxOverStakeFactor, _totalSupply, _stake, _avgStake);
    }

    function getDynamicCommissionByVoting(uint _votingId, uint _totalSupply, uint _stake)
        public
        view
        returns (uint)
    {
        return Helper.calculateDynamicCommission(dynamicFeeLinearRate, dynamicFeeLinearPrecision, maxOverStakeFactor, _totalSupply, _stake, votingMap[_votingId].avgStake);
    }

    function getVoting(uint _votingId)
        public
        view
        onlyVotingExists(_votingId)
        returns (
            uint itemId,
            uint fixedFee,
            uint movingSpeed,
            uint avgStake,
            uint commitEndTime,
            uint revealEndTime,
            uint totalPrize,
            uint votesUp,
            uint votesDown,
            bool calculated,
            address[] votersAddresses
        )
    {
        Voting storage voting = votingMap[_votingId];
        return (
            voting.itemId,
            voting.fixedFee,
            voting.movingSpeed,
            voting.avgStake,
            voting.commitEndTime,
            voting.revealEndTime,
            voting.totalPrize,
            voting.votesUp,
            voting.votesDown,
            voting.calculated,
            voting.votersAddresses
        );
    }

    function getVoterInfo(uint _votingId, address _voter)
        public
        view
        onlyVotingExists(_votingId)
        returns (
            bytes32 commitment,
            uint direction,
            uint stake,
            uint unstaked,
            uint reward,
            bool rewardClaimed
        )
    {
        VoterInfo storage info = votingMap[_votingId].voters[_voter];
        return (
            info.commitment,
            info.direction,
            info.stake,
            info.unstaked,
            info.reward,
            info.rewardClaimed
        );
    }

    function getVotingState(uint _votingId)
        public
        view
        onlyVotingExists(_votingId)
        returns (VotingState)
    {
        Voting memory voting = votingMap[_votingId];

        if (voting.calculated)
            return VotingState.Calculated;
        if (voting.revealEndTime < now)
            return VotingState.Finished;
        if (voting.commitEndTime < now)
            return VotingState.Revealing;

        return VotingState.Commiting;
    }

    function getVoters(uint _votingId)
        public
        view
        onlyVotingExists(_votingId)
        returns (address[])
    {
        return votingMap[_votingId].votersAddresses;
    }

    function getTotalWinnersStakes(uint _votingId)
        public
        view
        onlyWhenCalculated(_votingId)
        returns (uint)
    {
        if (votingMap[_votingId].votesUp > votingMap[_votingId].votesDown) {
            return votingMap[_votingId].votesUp;
        } else {
            return votingMap[_votingId].votesDown;
        }
    }

    function getVoterStake(uint _votingId, address _voter)
        public
        view
        returns (uint)
    {
        return votingMap[_votingId].voters[_voter].stake;
    }

    function getRewardSize(uint _votingId, address _voter)
        public
        view
        onlyWhenCalculated(_votingId)
        returns (uint reward)
    {
        return votingMap[_votingId].voters[_voter].reward;
    }

    function getVotingResult(uint _votingId)
        public
        view
        onlyWhenCalculated(_votingId)
        returns (uint8 result)
    {
        if (votingMap[_votingId].votesUp > votingMap[_votingId].votesDown)
            return 1;
        else
            return 0;
    }

    function isWinner(uint _votingId, address _voter)
        public
        view
        onlyWhenCalculated(_votingId)
        returns (bool)
    {
        Voting storage voting = votingMap[_votingId];

        if (voting.voters[_voter].stake == 0)
            return false;

        if (voting.votesUp > voting.votesDown) {
            return (1 == voting.voters[_voter].direction);
        }

        return (0 == voting.voters[_voter].direction);
    }


    // =================
    // VOTING INTERFACE
    // =================

    function startVoting(uint _itemId, uint _bounty, uint _commitTtl, uint _revealTtl, uint _movingSpeed, uint _avgStake, uint _maxRank, uint _itemRank)
        public
        onlyForRanking
        returns (uint votingId)
    {
        votingNonce = votingNonce + 1;

        uint commitEndTime = block.timestamp.add(_commitTtl);
        uint revealEndTime = commitEndTime.add(_revealTtl);

        Voting storage voting = votingMap[votingNonce];
        voting.itemId = _itemId;
        voting.commitEndTime = commitEndTime;
        voting.revealEndTime = revealEndTime;
        voting.movingSpeed = _movingSpeed;
        voting.avgStake = _avgStake;
        voting.totalPrize = _bounty;
        voting.fixedFee = Helper.calculateFixedCommission(maxFixedFeeRate, maxFixedFeePrecision, _avgStake, _maxRank, _itemRank);

        emit VotingCreated(_itemId, votingNonce, commitEndTime, revealEndTime);

        return votingNonce;
    }

    function commitVote(uint _votingId, bytes32 _secretHash, address _voter)
        public
        onlyForRanking
        onlyVotingExists(_votingId)
        onlyWhenCommit(_votingId)
        returns (uint forPay)
    {
        require(_secretHash != 0);
        require(votingMap[_votingId].voters[_voter].commitment == 0);

        votingMap[_votingId].votersAddresses.push(_voter);
        votingMap[_votingId].voters[_voter].commitment = _secretHash;
        votingMap[_votingId].totalPrize = votingMap[_votingId].totalPrize.add(votingMap[_votingId].fixedFee);

        emit VoteCommitted(votingMap[_votingId].itemId, _votingId, _voter);

        return votingMap[_votingId].fixedFee;
    }

    function revealVote(uint _votingId, uint _direction, uint _stake, uint _salt, address _voter, uint _totalSupply)
        public
        onlyForRanking
        onlyVotingExists(_votingId)
        onlyWhenReveal(_votingId)
        returns (uint forPay)
    {
        Voting storage voting = votingMap[_votingId];
        require(voting.voters[_voter].commitment != 0);
        require(voting.voters[_voter].stake == 0);
        require(_stake != 0);
        require(Helper.getCommitHash(_direction, _stake, _salt) == voting.voters[_voter].commitment);

        uint fee = Helper.calculateDynamicCommission(dynamicFeeLinearRate, dynamicFeeLinearPrecision, maxOverStakeFactor, _totalSupply, _stake, voting.avgStake);
        voting.voters[_voter].stake = _stake;
        voting.totalPrize = voting.totalPrize.add(fee);

        voting.voters[_voter].direction = _direction;

        if (_direction == 1) {
            voting.votesUp = voting.votesUp.add(_stake);
        } else {
            voting.votesDown = voting.votesDown.add(_stake);
        }

        emit VoteRevealed(voting.itemId, _votingId, _voter, _direction, _stake, _salt);

        return fee.add(_stake);
    }

    function finishVoting(uint _votingId)
        public
        onlyForRanking
        onlyVotingExists(_votingId)
        onlyWhenFinished(_votingId)
        returns (
            uint direction,
            uint distance,
            uint speed
        )
    {
        Voting storage voting = votingMap[_votingId];

        uint winnerDirection;
        uint winnersStakes;
        uint _distance;

        if (voting.votesUp > voting.votesDown) {
            winnerDirection = 1;
            winnersStakes = voting.votesUp;
            _distance = voting.votesUp - voting.votesDown;
        } else {
            winnerDirection = 0;
            winnersStakes = voting.votesDown;
            _distance = voting.votesDown - voting.votesUp;
        }

        voting.calculated = true;

        for (uint i = 0; i < voting.votersAddresses.length; ++i) {
            if (isWinner(_votingId, voting.votersAddresses[i])) {
                uint reward = Helper.calculatePrize(voting.totalPrize,
                    winnersStakes, voting.voters[voting.votersAddresses[i]].stake);

                voting.voters[voting.votersAddresses[i]].reward = reward;
            }
        }

        return (winnerDirection, _distance, voting.movingSpeed);
    }

    function removeVoting(uint _votingId)
        public
        onlyForRanking
        onlyVotingExists(_votingId)
        onlyWhenCalculated(_votingId)
    {
        delete votingMap[_votingId];
    }

    function claimReward(uint _votingId, address _voter)
        public
        onlyForRanking
        onlyWhenCalculated(_votingId)
        returns (uint)
    {
        if (votingMap[_votingId].voters[_voter].reward == 0)
            return 0;

        if (votingMap[_votingId].voters[_voter].rewardClaimed)
            return 0;

        votingMap[_votingId].voters[_voter].rewardClaimed = true;
        return votingMap[_votingId].voters[_voter].reward;
    }

    function unstakeAll(uint _votingId, address _voter)
        public
        onlyForRanking
        onlyWhenCalculated(_votingId)
        returns (uint)
    {
        uint res = votingMap[_votingId].voters[_voter].stake.sub(votingMap[_votingId].voters[_voter].unstaked);
        votingMap[_votingId].voters[_voter].unstaked = votingMap[_votingId].voters[_voter].stake;
        return res;
    }

    function unstake(uint _votingId, address _voter, uint _unstakeSize)
        public
        onlyForRanking
        onlyWhenCalculated(_votingId)
        returns (uint)
    {
        if (votingMap[_votingId].voters[_voter].unstaked > _unstakeSize)
            return 0;

        if (_unstakeSize > votingMap[_votingId].voters[_voter].stake)
            return 0;

        uint res = _unstakeSize.sub(votingMap[_votingId].voters[_voter].unstaked);
        votingMap[_votingId].voters[_voter].unstaked = _unstakeSize;
        return res;
    }
}