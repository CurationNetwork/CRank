pragma solidity ^0.4.24;


import "zeppelin/ownership/Ownable.sol";
import "plcr-revival/PLCRVoting.sol";
import "tokens/eip20/EIP20Interface.sol";
import "zeppelin/math/SafeMath.sol";
import "sol-tcr/contracts/Registry.sol";

/**
 * Based on Registry contract by skmgoldin
 * https://github.com/skmgoldin/tcr
 *
 * Original license: https://github.com/skmgoldin/tcr/blob/master/LICENSE.txt (Apache-2.0)
 */


contract RankedRegistry is Registry, Ownable /*temporary, for tests*/ {
    using SafeMath for uint;

    struct DappMeta {
        uint id;
        bytes32 hash;
        uint listPosition;
    }


    mapping(bytes32 => DappMeta) public dappsMetas;
    bytes32[] public listingHashes;

    function addDappMetaTemp(bytes32 _listingHash, uint _id, bytes32 _dataHash) public onlyOwner {

        listingHashes.push(_listingHash);
        dappsMetas[_listingHash] = DappMeta(
            _id,
            _dataHash,
            listingHashes.length-1
        );

        listings[_listingHash] = Listing (
            0,
            true,
            msg.sender,
            0,
            0
        );
    }

    /**
     * Return ids of whitelisted dapps
     */
    function getDapps(uint offset, uint limit)
        public
        view
        returns (bytes32[] _listingHashes, uint[] _ids, bytes32[] _dataHashes, bool[] _whitelisted)
    {
        require(offset < listingHashes.length);

        if (limit == 0) {
            limit = listingHashes.length - offset;
        }

        require(offset.add(limit) <= listingHashes.length);

        _listingHashes = new bytes32[](limit);
        _ids = new uint[](limit);
        _dataHashes = new bytes32[](limit);
        _whitelisted = new bool[](limit);
        for(uint i=offset; i<offset.add(limit); i++) {
            _listingHashes[i.sub(offset)] = listingHashes[i];
            _ids[i.sub(offset)]           = dappsMetas[ listingHashes[i] ].id;
            _dataHashes[i.sub(offset)]    = dappsMetas[ listingHashes[i] ].hash;
            _whitelisted[i.sub(offset)]   = listings[ listingHashes[i] ].whitelisted;

        }
    }


    /**************************** Registry ****************************/

    function apply(
        bytes32 _listingHash, uint _amount, string _data,
        uint _catalogId, bytes32 _catalogContentHash // <- from external catalog
    ) external {
        this.apply(_listingHash, _amount, _data);

        listingHashes.push(_listingHash);
        dappsMetas[_listingHash] = DappMeta(
            _catalogId,
            _catalogContentHash,
            listingHashes.length-1
        );
    }

    /**
     * Added removing elements from meta
     */
    function resetListing(bytes32 _listingHash) internal {
        super.resetListing(_listingHash);

        uint deletingPosition = dappsMetas[_listingHash].listPosition;

        if (deletingPosition != listingHashes.length-1) {
            listingHashes[ deletingPosition ] = listingHashes[ listingHashes.length-1 ];
            dappsMetas[ listingHashes[ deletingPosition ] ].listPosition = deletingPosition;
        }
        listingHashes.length = listingHashes.length-1;

        delete dappsMetas[_listingHash];
    }


}
