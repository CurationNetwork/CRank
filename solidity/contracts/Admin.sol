pragma solidity ^0.4.23;

import 'zeppelin-solidity/contracts/ownership/Superuser.sol';

contract Admin is Superuser {
    constructor() public {}

    function addAdmin(address newAdmin)
        public
        onlyOwner
    {
        addRole(newAdmin, ROLE_SUPERUSER);
    }

    function removeAdmin(address admin)
        public
        onlyOwner
    {
        addRole(admin, ROLE_SUPERUSER);
    }
}
