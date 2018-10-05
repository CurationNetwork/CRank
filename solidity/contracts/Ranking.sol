pragma solidity ^0.4.23;

import 'zeppelin-solidity/contracts/token/ERC20/ERC20.sol';
import 'zeppelin-solidity/contracts/math/SafeMath.sol';
import './IVoting.sol';
import './Admin.sol';
import './Helper.sol';


contract Ranking {

    using SafeMath for uint;

    event VotingStarted(
        uint itemId,
        uint votingId,
        uint startTime
    );

    event VoteCommit(
        uint itemId,
        uint votingId,
        address voter
    );

    event VoteReveal(
        uint itemId,
        uint votingId,
        address voter,
        uint direction,
        uint stake
    );

    event VotingFinished(
        uint itemId,
        uint votingId
    );

    event MovingStarted(
        uint itemId,
        uint votingId,
        uint movingId,
        uint startTime,
        uint distance,
        uint direction,
        uint speed
    );

    event MovingRemoved(
        uint _itemId,
        uint votingId,
        uint movingId
    );


    enum ItemState { None, Voting }
    enum VotingState { Commiting, Revealing, Finished }


    struct VoterInfo {
        uint direction;
        uint stake;
        uint unstaked;
        uint prize;
        bool isWinner;
    }

    struct Voting {
        uint fixedFee;
        uint unstakeSpeed;
        uint commitTtl;
        uint revealTtl;
        uint startTime;
        uint totalPrize;
        uint pollId;
        uint avgStake;

        address[] votersAddresses;
        mapping (address => VoterInfo) voters;
    }

    struct Moving {
        uint startTime;
        uint speed;
        uint distance;
        uint direction;
        uint votingId;
    }

    struct Item {
        uint id;
        address owner;
        uint lastRank;
        uint balance;
        uint votingId;
        uint[] movingsIds;
    }

    mapping (uint => Item) public Items;
    uint[] public ItemsIds;

    uint public VotingsLastId = 1;
    mapping (uint => Voting) public Votings;

    uint public MovingsLastId = 1;
    mapping (uint => Moving) public Movings;


    uint public stakesCounter = 1;
    uint public maxRank;
    uint public avgStake;

    IVoting votingContract;
    Admin accessContract;
    ERC20 tokenContract;


    /* constants */
    uint public dynamicFeeLinearRate;
    uint public dynamicFeeLinearPrecision;
    uint public maxOverStakeFactor;

    uint public maxFixedFeeRate;
    uint public maxFixedFeePrecision;

    uint public initialUnstakeSpeed;

    uint public currentCommitTtl;
    uint public currentRevealTtl;


    constructor(address accessContractAddress) public {
        accessContract = Admin(accessContractAddress);
    }

    function init(address votingContractAddress, address tokenContractAddress,
                uint dynamicFeeLinearRate_, uint dynamicFeeLinearPrecision_, uint maxOverStakeFactor_,
                uint maxFixedFeeRate_, uint maxFixedFeePrecision_, uint initialUnstakeSpeed_,
                uint currentCommitTtl_, uint currentRevealTtl_, uint initialAvgStake_
    )
        public
        onlyOwner
    {
        votingContract = IVoting(votingContractAddress);
        tokenContract = ERC20(tokenContractAddress);

        dynamicFeeLinearRate = dynamicFeeLinearRate_;
        dynamicFeeLinearPrecision = dynamicFeeLinearPrecision_;
        maxOverStakeFactor = maxOverStakeFactor_;

        maxFixedFeeRate = maxFixedFeeRate_;
        maxFixedFeePrecision = maxFixedFeePrecision_;

        initialUnstakeSpeed = initialUnstakeSpeed_;

        currentCommitTtl = currentCommitTtl_;
        currentRevealTtl = currentRevealTtl_;

        avgStake = initialAvgStake_;
    }


    /* MODIFIERS */
    modifier onlyExistItem(uint _itemId) {
        require(Items[_itemId].owner != address(0));
        _;
    }

    modifier onlyNotExistItem(uint _itemId) {
        require(Items[_itemId].owner == address(0));
        _;
    }

    modifier onlyExistVoting(uint votingId) {
        require(Votings[votingId].startTime != 0);
        _;
    }

    modifier onlyExistMoving(uint movingId) {
        require(Movings[movingId].startTime != 0);
        _;
    }

    modifier onlyItemOwner(uint _itemId) {
        require(Items[_itemId].owner == msg.sender);
        _;
    }

    modifier onlyFinishedVoting(uint votingId) {
        require(getVotingState(votingId) == VotingState.Finished);
        _;
    }

    modifier onlyOwner {
        require(accessContract.isOwner(msg.sender));
        _;
    }

    modifier onlySuperuser {
        require(accessContract.isSuperuser(msg.sender));
        _;
    }


    /* VIEW FUNCTIONS */
    function getItemState(uint _itemId)
        public
        view
        onlyExistItem(_itemId)
        returns (ItemState)
    {
        Item storage item = Items[_itemId];

        if (item.votingId == 0)
            return ItemState.None;
        else
            return ItemState.Voting;
    }

    function getVotingState(uint _votingId)
        public
        view
        onlyExistVoting(_votingId)
        returns (VotingState)
    {
        Voting storage voting = Votings[_votingId];

        if (voting.startTime + voting.commitTtl + voting.revealTtl < now)
            return VotingState.Finished;
        if (voting.startTime + voting.commitTtl < now)
            return VotingState.Revealing;

        return VotingState.Commiting;
    }

    function getFixedCommission(uint _itemId)
        public
        view
        onlyExistItem(_itemId)
        returns (uint)
    {
        uint maxFee = avgStake.mul(maxFixedFeeRate).div(maxFixedFeePrecision);
        uint itemRank = getCurrentRank(_itemId);

        if (itemRank >= maxRank)
            return maxFee;

        uint dRank = maxRank.sub(itemRank);

        return maxFee.sub(maxFee.mul(dRank).div(maxRank));
    }

    function getDynamicCommission(uint _stake, uint _avgStake)
        public
        view
        returns (uint)
    {
        if (_stake <= _avgStake)
            return _stake.mul(dynamicFeeLinearRate).div(dynamicFeeLinearPrecision);

        uint overStake = _stake.sub(_avgStake);
        uint fee = _avgStake.mul(dynamicFeeLinearRate).div(dynamicFeeLinearPrecision);

        uint k = 1;
        uint kPrecision = 1;
        uint max = Helper.sqrt(tokenContract.totalSupply().sub(_avgStake));
        uint x = maxOverStakeFactor.mul(_avgStake);

        if (max > x)
            k = max.div(x);
        else
            kPrecision = x.div(max);

        return fee.add(k.mul(overStake).div(kPrecision) ** 2);
    }

    function getRankForTimestamp(uint _itemId, uint _timestamp)
        public
        view
        onlyExistItem(_itemId)
        returns (uint)
    {
        Item storage item = Items[_itemId];

        uint rank = item.lastRank;

        for (uint i = 0; i < item.movingsIds.length; ++i) {
            Moving storage moving = Movings[item.movingsIds[i]];

            if (_timestamp.sub(moving.startTime).mul(moving.speed) >= moving.distance) {
                if (moving.direction != 0)
                    rank = rank.add(moving.distance);
                else
                    rank = rank.sub(moving.distance);
            }
            else {
                if (moving.direction != 0)
                    rank = rank.add(_timestamp.sub(moving.startTime).mul(moving.speed));
                else
                    rank = rank.sub(_timestamp.sub(moving.startTime).mul(moving.speed));
            }
        }

        return rank;
    }

    function getCurrentRank(uint _itemId)
        public
        view
        returns (uint)
    {
        return getRankForTimestamp(_itemId, now);
    }

    function getUnstakeSpeed()
        public
        view
        returns (uint)
    {
        return initialUnstakeSpeed;  //TODO dynamic change
    }

    function getItemsWithRank()
        public
        view
        returns (
            uint[] ids,
            uint[] ranks
        )
    {
        uint[] memory _ranks = new uint[](ItemsIds.length);

        for (uint i = 0; i < ItemsIds.length; i++)
            _ranks[i] = getCurrentRank(ItemsIds[i]);

        return (
            ItemsIds,
            _ranks
        );
    }

    function getItem(uint _itemId)
        public
        view
        onlyExistItem(_itemId)
        returns (
            address owner,
            uint lastRank,
            uint balance,
            uint votingId,
            uint[] movingsIds
        )
    {
        Item storage item = Items[_itemId];
        return (
            item.owner,
            item.lastRank,
            item.balance,
            item.votingId,
            item.movingsIds
        );
    }

    function getVoting(uint _votingId)
        public
        view
        onlyExistVoting(_votingId)
        returns (
            uint fixedFee,
            uint unstakeSpeed,
            uint commitTtl,
            uint revealTtl,
            uint startTime,
            uint totalPrize,
            uint avgStake,
            address[] votersAddresses
        )
    {
        Voting storage voting = Votings[_votingId];
        return (
            voting.fixedFee,
            voting.unstakeSpeed,
            voting.commitTtl,
            voting.revealTtl,
            voting.startTime,
            voting.totalPrize,
            voting.avgStake,
            voting.votersAddresses
        );
    }

    function getVoterInfo(uint _votingId, address _voter)
        public
        view
        onlyExistVoting(_votingId)
        returns (
            uint direction,
            uint stake,
            uint unstaked,
            uint prize,
            bool isWinner
        )
    {
        VoterInfo storage info = Votings[_votingId].voters[_voter];
        return (
            info.direction,
            info.stake,
            info.unstaked,
            info.prize,
            info.isWinner
        );
    }

    function getMoving(uint _movingId)
        public
        view
        onlyExistMoving(_movingId)
        returns (
            uint startTime,
            uint speed,
            uint distance,
            uint direction,
            uint votingId
        )
    {
        Moving storage moving = Movings[_movingId];
        return (
            moving.startTime,
            moving.speed,
            moving.distance,
            moving.direction,
            moving.votingId
        );
    }


    /* Only owner functions (only for testing period) */
    function newItemsWithRanks(uint[] _ids, uint[] _ranks)
        public
        onlySuperuser
    {
        require(_ids.length == _ranks.length);

        for (uint i = 0; i < _ids.length; i++) {
            Item storage item = Items[_ids[i]];
            require(item.owner == address(0));

            ItemsIds.push(_ids[i]);
            item.owner = msg.sender;
            item.lastRank = _ranks[i];

            avgStake = Helper.calculateNewAvgStake(avgStake, _ranks[i], stakesCounter++);
        }
    }

    function setItemLastRank(uint _itemId, uint _rank)
        public
        onlySuperuser
        onlyExistItem(_itemId)
    {
        Item storage item = Items[_itemId];
        item.lastRank = _rank;
    }

    function setUnstakeSpeed(uint _speed)
        public
        onlySuperuser
    {
        initialUnstakeSpeed = _speed;
    }

    function setTtl(uint _commitTtl, uint _revealTtl)
        public
        onlySuperuser
    {
        currentCommitTtl = _commitTtl;
        currentRevealTtl = _revealTtl;
    }


    /* LISTING FUNCTIONS */
    function newItem(uint _id)
        public
        onlyNotExistItem(_id)
    {
        Item storage item = Items[_id];
        ItemsIds.push(_id);

        item.owner = msg.sender;
    }

    function chargeBalance(uint _itemId, uint _numTokens)
        public
        onlyItemOwner(_itemId)
    {
        require(getItemState(_itemId) == ItemState.None);

        Items[_itemId].balance += _numTokens;
        require(pay(msg.sender, _numTokens));
    }


    /* VOTING FUNCTIONS */
    function voteCommit(uint _itemId, bytes32 _commitment)
        public
        onlyExistItem(_itemId)
    {
        Item storage item = Items[_itemId];

        if (item.votingId == 0) {
            item.votingId = newVoting(_itemId);

            emit VotingStarted(_itemId, item.votingId, now);
        }

        require(getVotingState(item.votingId) == VotingState.Commiting);
        Voting storage voting = Votings[item.votingId];

        require(pay(msg.sender, voting.fixedFee));
        voting.totalPrize = voting.totalPrize.add(voting.fixedFee);

        voting.votersAddresses.push(msg.sender);

        votingContract.commitVote(voting.pollId, _commitment, msg.sender);

        removeOldMovings(_itemId);

        emit VoteCommit(_itemId, item.votingId, msg.sender);
    }

    function voteReveal(uint _itemId, uint8 _direction, uint _stake, uint _salt)
        public
        onlyExistItem(_itemId)
    {
        Item storage item = Items[_itemId];
        require(getItemState(_itemId) == ItemState.Voting);
        require(getVotingState(item.votingId) == VotingState.Revealing);

        Voting storage voting = Votings[item.votingId];

        uint fee = getDynamicCommission(_stake, voting.avgStake);
        require(pay(msg.sender, fee.add(_stake)));
        voting.totalPrize = voting.totalPrize.add(fee);

        VoterInfo storage voterInfo = voting.voters[msg.sender];
        voterInfo.stake = _stake;
        voterInfo.direction = _direction;

        votingContract.revealVote(voting.pollId, _direction, _stake, _salt, msg.sender);

        avgStake = Helper.calculateNewAvgStake(avgStake, _stake, stakesCounter++);

        emit VoteReveal(_itemId, item.votingId, msg.sender, _direction, _stake);
    }

    function finishVoting(uint _itemId)
        public
        onlyExistItem(_itemId)
    {
        require(getItemState(_itemId) == ItemState.Voting);
        require(getVotingState(Items[_itemId].votingId) == VotingState.Finished);

        Item storage item = Items[_itemId];

        sendPrizesOrUnstake(item.votingId);

        Voting storage voting = Votings[item.votingId];

        uint votesUp;
        uint votesDown;
        (votesUp, votesDown) = votingContract.getPollResult(voting.pollId);

        uint _direction = votesUp > votesDown ? 1 : 0;
        uint distance = votesUp > votesDown ? votesUp - votesDown : votesDown - votesUp;

        if (_direction == 0) {
            distance = distanceWithCheckUnderZero(_itemId, distance, voting.unstakeSpeed);
        }

        uint movingId = newMoving(now, voting.unstakeSpeed, distance, _direction, item.votingId);
        item.movingsIds.push(movingId);
        item.votingId = 0;

        emit MovingStarted(_itemId, item.votingId, movingId, now, distance, _direction, voting.unstakeSpeed);

        emit VotingFinished(_itemId, item.votingId);
    }

    function unstake(uint _itemId)
        public
    {
        for (uint i = 0; i < Items[_itemId].movingsIds.length; ++i) {
            Moving storage moving = Movings[Items[_itemId].movingsIds[i]];

            if (Votings[moving.votingId].voters[msg.sender].stake != 0) {
                VoterInfo storage voterInfo = Votings[moving.votingId].voters[msg.sender];

                if (voterInfo.stake <= voterInfo.unstaked)
                    continue;

                if ((now.sub(moving.startTime)).mul(moving.speed) >= moving.distance) {
                    require(send(msg.sender, voterInfo.stake - voterInfo.unstaked));
                    voterInfo.unstaked = voterInfo.stake;
                }
                else {
                    uint movedDistance = now.sub(moving.startTime).mul(moving.speed);
                    uint forUnstake = voterInfo.stake.mul(movedDistance).div(moving.distance);

                    if (forUnstake > voterInfo.unstaked) {
                        require(send(msg.sender, forUnstake - voterInfo.unstaked));
                        voterInfo.unstaked = forUnstake;
                    }
                }
            }
        }
    }


    /* INTERNAL FUNCTIONS */
    function newVoting(uint _itemId)
        internal
        returns (uint)
    {
        uint votingId = VotingsLastId++;
        Voting storage voting = Votings[votingId];
        Item storage item = Items[_itemId];

        voting.startTime = now;
        voting.fixedFee = getFixedCommission(_itemId);
        voting.unstakeSpeed = getUnstakeSpeed();
        voting.commitTtl = currentCommitTtl;
        voting.revealTtl = currentRevealTtl;
        voting.avgStake = avgStake;

        voting.totalPrize = item.balance;
        item.balance = 0;


        voting.pollId = votingContract.startPoll(
            _itemId,
            voting.commitTtl,
            voting.revealTtl
        );

        return votingId;
    }

    function newMoving(uint _startTime, uint _speed, uint _distance, uint _direction, uint _votingId)
        internal
        returns (uint)
    {
        uint movingId = MovingsLastId++;
        Moving storage moving = Movings[movingId];

        moving.startTime = _startTime;
        moving.speed = _speed;
        moving.distance = _distance;
        moving.direction = _direction;
        moving.votingId = _votingId;

        return movingId;
    }

    function removeOldMovings(uint _itemId)
        internal
    {
        Item storage item = Items[_itemId];

        for (uint i = 0; i < item.movingsIds.length; ++i) {
            Moving storage moving = Movings[item.movingsIds[i]];

            if (now.sub(moving.startTime).mul(moving.speed) >= moving.distance) {
                unstakeForAllVoters(moving.votingId);

                if (moving.direction != 0)
                    item.lastRank = item.lastRank.add(moving.distance);
                else
                    item.lastRank = item.lastRank.sub(moving.distance);

                if (maxRank < item.lastRank)
                    maxRank = item.lastRank;

                emit MovingRemoved(_itemId, moving.votingId, item.movingsIds[i]);

                delete Votings[moving.votingId];
                delete Movings[item.movingsIds[i]];

                item.movingsIds[i] = item.movingsIds[item.movingsIds.length - 1];
                item.movingsIds.length--;
                i--;
            }
        }
    }

    function unstakeForAllVoters(uint _votingId)
        internal
    {
        Voting storage voting = Votings[_votingId];

        for (uint i = 0; i < voting.votersAddresses.length; ++i) {
            VoterInfo storage voter = voting.voters[voting.votersAddresses[i]];

            if (voter.stake > voter.unstaked) {
                require(send(voting.votersAddresses[i], voter.stake.sub(voter.unstaked)));
                voter.unstaked = voter.stake;
            }
        }
    }

    function sendPrizesOrUnstake(uint _votingId)
        internal
    {
        Voting storage voting = Votings[_votingId];

        for (uint i = 0; i < voting.votersAddresses.length; ++i) {
            if (votingContract.isWinner(voting.pollId, voting.votersAddresses[i])) {
                uint prize = Helper.calculatePrize(voting.totalPrize,
                                            votingContract.getOverallStake(voting.pollId),
                                            voting.voters[voting.votersAddresses[i]].stake);

                voting.voters[voting.votersAddresses[i]].isWinner = true;
                require(send(voting.votersAddresses[i], prize));
            }
            else {
                if (voting.voters[voting.votersAddresses[i]].stake > 0) {
                    require(send(voting.votersAddresses[i], voting.voters[voting.votersAddresses[i]].stake));
                    voting.voters[voting.votersAddresses[i]].unstaked = voting.voters[voting.votersAddresses[i]].stake;
                }
            }
        }
    }

    function distanceWithCheckUnderZero(uint _itemId, uint _distance, uint _speed)
        internal
        returns (uint)
    {
        Item storage item = Items[_itemId];

        uint minExpectedTime = _distance.div(_speed);
        bool hasActiveMoving = false;

        for (uint i = 0; i < item.movingsIds.length; ++i) {
            Moving storage moving = Movings[item.movingsIds[i]];

            uint finishTime = moving.startTime.add(moving.distance.div(moving.speed));
            if (finishTime > now) {
                hasActiveMoving = true;
                uint _time = getRankForTimestamp(_itemId, finishTime) / _speed;

                if (_time < minExpectedTime)
                    minExpectedTime = _time;
            }
        }

        if (!hasActiveMoving) {
            uint time = getRankForTimestamp(_itemId, finishTime) / _speed;
            if (time < minExpectedTime)
                minExpectedTime = time;
        }

        return minExpectedTime.mul(_speed);
    }

    function send(address _to, uint256 _value)
        internal
        returns (bool)
    {
        assert(_to != address(0));

        return tokenContract.transfer(_to, _value);
    }

    function pay(address _from, uint256 _value)
        internal
        returns (bool)
    {
        assert(_from != address(0));
        assert(_value <= tokenContract.allowance(_from, this));

        return tokenContract.transferFrom(_from, this, _value);
    }
}
