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
}
