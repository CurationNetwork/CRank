#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import time
import argparse
from queue import Queue
from urllib.request import urlopen, Request
import re
import json

import hashlib

import os.path

import web3
from web3 import Web3, HTTPProvider, TestRPCProvider
from solc import compile_source
# from web3.contract import ConciseContract


def main(arguments):

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # parser.add_argument('infile', help="Input file", type=argparse.FileType('r'))
    # parser.add_argument('-o', '--outfile', required=True, help="Output file to save JSON with parsed dapps")#, default=sys.stdout, type=argparse.FileType('w'))
    args = parser.parse_args(arguments)
    web3 = Web3(TestRPCProvider())

    registry = deploy_contract_and_get_instance(web3)

    # print('get dapps by id: {}'.format(registry.getDappbyId(1)))

    dapps_crawler = {}
    dapps_registry = {}
    c1 = 0
    MAX_DAPPS = 5
    with open('/tmp/dapps_dict_all', 'r') as json_file:
        dapps_crawler = json.load(json_file)
        for d in dapps_crawler:
            c1 = c1 + 1
            if c1 >= MAX_DAPPS:
                break
            dapp = None
            try:
                dapp = process_smartz_dapp(dapps_crawler[d])
            except Exception as e:
                print("[ERROR] Error processing dapp from crawler: {}".format(repr(e)))
                continue

            tx_hash = registry.functions.addDappMetaTemp(dapp['name'], 1, json.dumps(dapp)).transact()
            web3.eth.waitForTransactionReceipt(tx_hash)

    print("[DEBUG] {} dapps uploaded to contract".format(c1))
    # now lets check that all dapps are uploaded correctly

    dapps_ids = registry.functions.getDAppsIds().call()

    for dapp_id in dapps_ids:
        dapp = registry.functions.getDAppById(dapp_id).call()
        print(repr(dapp))

    # from contract source: [HZ] doesn't work
    # bytes32 id = keccak256(abi.encodePacked(_name, _metatype, _metadata));
    # abi_encoded = registry.encodeABI(fn_name='addDappMetaTemp', args=[name, metatype, metadata])
    # dapp_id = web3.sha3(hexstr=abi_encoded[2:])

    print("[FINISHED]")


# taken from crawler - the main function to validate dapp, ready for uploading into registry contract
def process_smartz_dapp(dapp):
    # copies only needed data from dapps, came from crawler

    result_dapp = {}
    mandatory_fields = ('name', 'url')
    for i in mandatory_fields:
        if dapp.get(i) is None:
            raise ValueError("Empty mandatory field '{}'(is None):".format(i))
        if isinstance(dapp[i], list) == True and len(dapp[i]) == 0:
            raise ValueError("Empty mandatory array '{}'".format(i))
        result_dapp[i] = dapp[i]

    # DApp must have at leas one address in any network
    addr_re = re.compile('^0x[0-9a-fA-F]{40}$')

    contracts = dapp.get('contracts')
    if contracts is None or len(contracts) == 0:
        raise ValueError("Empty mandatory 'contracts' dict(at least one address in any network must be present")

    for network in contracts:
        if (len(contracts[network]) == 0):
            raise ValueError("Empty array of addresses in 'contracts'({})".format(network))

        addresses = contracts[network]
        if (len(addresses) == 0):
            raise ValueError("No addresses in 'contracts'({})".format(network))

        for a in addresses:
            if (not addr_re.match(a)):
                raise ValueError("Invalid address '{}' in 'contracts'({})".format(a, network))
    result_dapp['contracts'] = dapp['contracts']

    return result_dapp

def deploy_contract_and_get_instance(web3): # web3 - web3 instance

    ################################################################
    # [UPLOAD TO CONTRACT] - remove dublicates, combine crawled dapps
    ################################################################
    # Solidity source code
    contract_source_code = '''
        pragma solidity ^0.4.24;

        // File: openzeppelin-solidity/contracts/ownership/Ownable.sol

        /**
         * @title Ownable
         * @dev The Ownable contract has an owner address, and provides basic authorization control
         * functions, this simplifies the implementation of "user permissions".
         */
        contract Ownable {
          address public owner;


          event OwnershipRenounced(address indexed previousOwner);
          event OwnershipTransferred(
            address indexed previousOwner,
            address indexed newOwner
          );


          /**
           * @dev The Ownable constructor sets the original `owner` of the contract to the sender
           * account.
           */
          constructor() public {
            owner = msg.sender;
          }

          /**
           * @dev Throws if called by any account other than the owner.
           */
          modifier onlyOwner() {
            require(msg.sender == owner);
            _;
          }

          /**
           * @dev Allows the current owner to relinquish control of the contract.
           * @notice Renouncing to ownership will leave the contract without an owner.
           * It will not be possible to call the functions with the `onlyOwner`
           * modifier anymore.
           */
          function renounceOwnership() public onlyOwner {
            emit OwnershipRenounced(owner);
            owner = address(0);
          }

          /**
           * @dev Allows the current owner to transfer control of the contract to a newOwner.
           * @param _newOwner The address to transfer ownership to.
           */
          function transferOwnership(address _newOwner) public onlyOwner {
            _transferOwnership(_newOwner);
          }

          /**
           * @dev Transfers control of the contract to a newOwner.
           * @param _newOwner The address to transfer ownership to.
           */
          function _transferOwnership(address _newOwner) internal {
            require(_newOwner != address(0));
            emit OwnershipTransferred(owner, _newOwner);
            owner = _newOwner;
          }
        }


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

            function getDAppsIds() public view returns(bytes32[] ) {
                return dappsIds;
            }

            function getDAppById(bytes32 _id) public view returns (string name, uint256 metatype, string metadata) {
                return (dapps[_id].name, dapps[_id].metatype, dapps[_id].metadata);
            }

            function addDappMetaTemp(string _name, uint _metatype, string _metadata) public returns(bytes32) {
                bytes32 id = keccak256(abi.encodePacked(_name, _metatype, _metadata));

                dappsIds.push(id);
                dapps[id] = DappMeta(
                    _name,
                    _metatype,
                    _metadata
                );
                return id;
            }

        }
    '''

    compiled_sol = compile_source(contract_source_code) # Compiled source code
    contract_interface = compiled_sol['<stdin>:RankedRegistry']

    # Instantiate and deploy contract
    RankedRegistry = web3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])

    tx_hash = RankedRegistry.constructor().transact({'from': web3.eth.accounts[0]})
    tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)

    # Get tx receipt to get contract address
    contract_address = tx_receipt['contractAddress']
    print("[DEBUG] Compiled contract is deployed at addr: {}".format(contract_address))

    abi = contract_interface['abi']
    return web3.eth.contract(address=contract_address, abi=abi)






if __name__ == '__main__':
    start = time.time()
    sys.exit(main(sys.argv[1:]))

