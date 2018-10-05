pragma solidity ^0.4.23;

import 'zeppelin-solidity/contracts/math/SafeMath.sol';


library Helper {

    using SafeMath for uint;

    function sqrt(uint x)
        public
        pure
        returns (uint y)
    {
        if (x == 0)
            return 0;
        else if (x <= 3)
            return 1;

        uint z = (x + 1) / 2;
        y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }

    function getCommitHash(uint _direction, uint _stake, uint _salt)
        public
        pure
        returns (bytes32)
    {
        return keccak256(abi.encodePacked(_direction, _stake, _salt));
    }

    function calculatePrize(uint _overallPrize, uint _overallStake, uint _voterStake)
        public
        pure
        returns (uint)
    {
        return _overallPrize.mul(_voterStake).div(_overallStake);
    }

    function calculateNewAvgStake(uint _oldAvgStake, uint _stake, uint _stakesCnt)
        public
        pure
        returns (uint)
    {
        uint newStakesCnt = _stakesCnt.add(1);
        return _oldAvgStake.div(newStakesCnt).mul(_stakesCnt).add(_stake.div(newStakesCnt));
    }

    function calculateFixedCommission(
        uint _maxFixedFeeRate, uint _maxFixedFeePrecision,
        uint _avgStake, uint _maxRank, uint _itemRank
    )
        public
        pure
        returns (uint)
    {
        uint maxFee = _avgStake.mul(_maxFixedFeeRate).div(_maxFixedFeePrecision);

        if (_itemRank >= _maxRank)
            return maxFee;

        uint dRank = _maxRank.sub(_itemRank);

        return maxFee.sub(maxFee.mul(dRank).div(_maxRank));
    }

    function calculateDynamicCommission(
        uint _dynamicFeeLinearRate, uint _dynamicFeeLinearPrecision,
        uint _maxOverStakeFactor, uint _totalSupply, uint _stake, uint _avgStake
    )
        public
        view
        returns (uint)
    {
        if (_stake <= _avgStake)
            return _stake.mul(_dynamicFeeLinearRate).div(_dynamicFeeLinearPrecision);

        uint overStake = _stake.sub(_avgStake);
        uint fee = _avgStake.mul(_dynamicFeeLinearRate).div(_dynamicFeeLinearPrecision);

        uint k = 1;
        uint kPrecision = 1;
        uint max = sqrt(_totalSupply.sub(_avgStake));
        uint x = _maxOverStakeFactor.mul(_avgStake);

        if (max > x)
            k = max.div(x);
        else
            kPrecision = x.div(max);

        return fee.add(k.mul(overStake).div(kPrecision) ** 2);
    }
}
