pragma solidity ^0.4.23;

import 'zeppelin-solidity/contracts/token/ERC20/ERC20.sol';
import 'zeppelin-solidity/contracts/math/SafeMath.sol';
import './Voting.sol';
import './Admin.sol';
import './Helper.sol';


contract Ranking {

    using SafeMath for uint;


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

    uint public MovingsLastId = 1;
    mapping (uint => Moving) public Movings;


    uint public stakesCounter = 0;
    uint public maxRank;
    uint public avgStake;

    Voting votingContract;
    Admin accessContract;
    ERC20 tokenContract;


    /* constants */
    uint public initialMovingSpeed;

    uint public currentCommitTtl;
    uint public currentRevealTtl;


    constructor(address accessContractAddress) public {
        accessContract = Admin(accessContractAddress);
    }

    function init(address votingContractAddress, address tokenContractAddress, uint initialMovingSpeed_,
                uint currentCommitTtl_, uint currentRevealTtl_, uint initialAvgStake_
    )
        public
        onlyOwner
    {
        votingContract = Voting(votingContractAddress);
        tokenContract = ERC20(tokenContractAddress);

        initialMovingSpeed = initialMovingSpeed_;

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

    modifier onlyExistMoving(uint movingId) {
        require(Movings[movingId].startTime != 0);
        _;
    }

    modifier onlyItemOwner(uint _itemId) {
        require(Items[_itemId].owner == msg.sender);
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

    function getFixedCommission(uint _itemId)
        public
        view
        onlyExistItem(_itemId)
        returns (uint)
    {
        return votingContract.getFixedCommission(avgStake, maxRank, getCurrentRank(_itemId));
    }

    function getDynamicCommission(uint _itemId, uint _stake)
        public
        view
        returns (uint)
    {
        if (Items[_itemId].votingId != 0) {
            return votingContract.getDynamicCommissionByVoting(Items[_itemId].votingId, tokenContract.totalSupply(), _stake);
        }

        return votingContract.getDynamicCommission(avgStake, tokenContract.totalSupply(), _stake);
    }

    function getRankForTimestamp(uint _itemId, uint _timestamp) // expect ts >= now
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

    function getMovingSpeed()
        public
        view
        returns (uint)
    {
        return initialMovingSpeed; //TODO dynamic change
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


    /* Only admin functions (only for testing period) */
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

            if (maxRank < _ranks[i])
                maxRank = _ranks[i];
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
        initialMovingSpeed = _speed;
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
        onlySuperuser
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
            item.votingId = votingContract.startVoting(_itemId, item.balance, currentCommitTtl, currentRevealTtl,
                getMovingSpeed(), avgStake, maxRank, getCurrentRank(_itemId));

            item.balance = 0;
        }

        require(votingContract.getVotingState(item.votingId) == Voting.VotingState.Commiting);

        require(pay(msg.sender, votingContract.commitVote(item.votingId, _commitment, msg.sender)));

        removeOldMovings(_itemId);
    }

    function voteReveal(uint _itemId, uint _direction, uint _stake, uint _salt)
        public
        onlyExistItem(_itemId)
    {
        Item storage item = Items[_itemId];
        require(getItemState(_itemId) == ItemState.Voting);
        require(votingContract.getVotingState(item.votingId) == Voting.VotingState.Revealing);

        require(pay(msg.sender, votingContract.revealVote(item.votingId, _direction, _stake, _salt, msg.sender, tokenContract.totalSupply())));

        avgStake = Helper.calculateNewAvgStake(avgStake, _stake, stakesCounter++);
    }

    function finishVoting(uint _itemId)
        public
        onlyExistItem(_itemId)
    {
        require(getItemState(_itemId) == ItemState.Voting);
        require(votingContract.getVotingState(Items[_itemId].votingId) == Voting.VotingState.Finished);

        Item storage item = Items[_itemId];

        var (direction, distance, speed) = votingContract.finishVoting(item.votingId);

        if (direction == 0) {
            distance = distanceWithCheckUnderZero(_itemId, distance, speed);
        }

        sendPrizesOrUnstake(item.votingId);

        uint movingId = newMoving(now, speed, distance, direction, item.votingId);
        item.movingsIds.push(movingId);
        item.votingId = 0;

        emit MovingStarted(_itemId, item.votingId, movingId, now, distance, direction, speed);
    }

    function unstake(uint _itemId)
        public
    {
        for (uint i = 0; i < Items[_itemId].movingsIds.length; ++i) {
            Moving storage moving = Movings[Items[_itemId].movingsIds[i]];

            uint stake = votingContract.getVoterStake(moving.votingId, msg.sender);

            if (stake != 0) {
                uint forUnstake = stake;

                uint movedDistance = now.sub(moving.startTime).mul(moving.speed);
                if (movedDistance < moving.distance) {
                    forUnstake = stake.mul(movedDistance).div(moving.distance);
                }

                require(send(msg.sender, votingContract.unstake(moving.votingId, msg.sender, forUnstake)));
            }
        }
    }

    function removeOldMovings(uint _itemId)
        public
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

                delete Movings[item.movingsIds[i]];
                votingContract.removeVoting(moving.votingId);

                item.movingsIds[i] = item.movingsIds[item.movingsIds.length - 1];
                item.movingsIds.length--;
                i--;
            }
        }
    }

    /* INTERNAL FUNCTIONS */

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

    function unstakeForAllVoters(uint _votingId)
        internal
    {
        address[] memory voters = votingContract.getVoters(_votingId);

        for (uint i = 0; i < voters.length; ++i) {
            uint stake = votingContract.getVoterStake(_votingId, voters[i]);
            if (stake > 0) {
                require(send(voters[i], votingContract.unstake(_votingId, voters[i], stake)));
            }
        }
    }

    event DebugLoose (address voter, uint stake);
    event DebugWin (address voter, uint reward);
    event DebugLength (uint l, uint votingId);

    function sendPrizesOrUnstake(uint _votingId)
        internal
    {
        address[] memory voters = votingContract.getVoters(_votingId);

        emit DebugLength(voters.length, _votingId);

        for (uint i = 0; i < voters.length; ++i) {
            if (votingContract.isWinner(_votingId, voters[i])) {
                uint reward = votingContract.claimReward(_votingId, voters[i]);
                emit DebugWin(voters[i], reward);
                require(send(voters[i], reward));
            }
            else {
                uint stake = votingContract.unstakeAll(_votingId, voters[i]);
                emit DebugLoose(voters[i], stake);
                require(send(voters[i], stake));
            }
        }
    }

    function distanceWithCheckUnderZero(uint _itemId, uint _distance, uint _speed)
        internal
        view
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

        if (_value == 0)
            return true;

        return tokenContract.transfer(_to, _value);
    }

    function pay(address _from, uint256 _value)
        internal
        returns (bool)
    {
        assert(_from != address(0));
        assert(_value <= tokenContract.allowance(_from, this));

        if (_value == 0)
            return true;

        return tokenContract.transferFrom(_from, this, _value);
    }
}
