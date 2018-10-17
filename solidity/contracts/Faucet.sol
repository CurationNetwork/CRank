pragma solidity ^0.4.23;

import 'zeppelin-solidity/contracts/token/ERC20/StandardToken.sol';
import 'zeppelin-solidity/contracts/math/SafeMath.sol';
import './Admin.sol';

contract Faucet {

    using SafeMath for uint;

    event FaucetSended(
        address receiver,
        uint amount
    );

    StandardToken token;
    Admin accessContract;
    mapping (bytes32 => bool) codeHashes;
    mapping (byte => bool) allowedChars;

    uint public faucetSize;


    constructor(address accessContractAddress) public {
        accessContract = Admin(accessContractAddress);
    }

    modifier onlyOwner {
        require(accessContract.isOwner(msg.sender));
        _;
    }

    modifier onlySuperuser {
        require(accessContract.isSuperuser(msg.sender));
        _;
    }


    function init(address tokenAddress)
        public
        onlyOwner
    {
        token = StandardToken(tokenAddress);
    }


    function getBalance()
        view
        public
        returns (uint)
    {
        return token.balanceOf(this);
    }


    function setCharset(string charset)
        public
        onlyOwner
    {
        bytes memory str = bytes(charset);

        for (uint i = 0; i < str.length; ++i) {
            allowedChars[str[i]] = true;
        }
    }

    function setCodeHashes(bytes32[] hashes)
        public
        onlySuperuser
    {
        for (uint i = 0; i < hashes.length; ++i) {
            codeHashes[hashes[i]] = true;
        }
    }

    function setFaucetSize(uint newSize)
        public
        onlySuperuser
    {
        faucetSize = newSize;
    }


    function checkCode(string code)
        view
        returns (bool)
    {
        bytes memory str = bytes(code);

        if (str.length != 7)
            return false;

        for (uint i = 0; i < str.length; ++i) {
            if (!allowedChars[str[i]])
                return false;
        }

        return codeHashes[sha3(code)];
    }

    function faucet(string code)
        public
    {
        require(checkCode(code));
        require(faucetSize <= getBalance(), "faucet balance not enough");

        delete codeHashes[sha3(code)];

        require(token.transfer(msg.sender, faucetSize));
        emit FaucetSended(msg.sender, faucetSize);
    }

    function destruct()
        public
        onlyOwner
    {
        require(token.transfer(msg.sender, getBalance()));
        selfdestruct(msg.sender);
    }
}
