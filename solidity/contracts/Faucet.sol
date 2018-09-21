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
    mapping (address => uint) lastFaucets;

    uint public faucetSize;
    uint public faucetRate;


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

    function getLastFaucet(address target)
        view
        public
        returns (uint)
    {
        return lastFaucets[target];
    }



    function setFaucetRate(uint newRate)
        public
        onlyOwner
    {
        faucetRate = newRate;
    }

    function setFaucetSize(uint newSize)
        public
        onlyOwner
    {
        faucetSize = newSize;
    }

    function faucet()
        public
    {
        if (!accessContract.isSuperuser(msg.sender)) {
            require(lastFaucets[msg.sender].add(faucetRate) < now, "faucet rate limit");
        }

        require(faucetSize <= getBalance(), "faucet balance not enough");

        lastFaucets[msg.sender] = now;
        require(token.transfer(msg.sender, faucetSize));
        emit FaucetSended(msg.sender, faucetSize);
    }
}
