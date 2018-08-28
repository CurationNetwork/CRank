pragma solidity ^0.4.24;

import "openzeppelin-solidity/contracts/ownership/Ownable.sol";

/**
 * Based on Registry contract by skmgoldin
 * https://github.com/skmgoldin/tcr
 *
 * Original license: https://github.com/skmgoldin/tcr/blob/master/LICENSE.txt (Apache-2.0)
 */


contract RankedRegistry is Ownable /*temporary, for tests*/ {

    struct DappMeta {
        string name;
        uint256 metatype;
        string metadata;
    }

    mapping (bytes32 => DappMeta) public dapps;
    bytes32[] public dappsIds;

    function addDappMetaTemp(string _name, uint _metatype, string _metadata) public onlyOwner {
        bytes32 id = keccak256(abi.encodePacked(_name, _metatype, _metadata));

        dappsIds.push(id);
        dapps[id] = DappMeta(
            _name,
            _metatype,
            _metadata
        );
    }

}
