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
from web3.contract import ConciseContract
from web3.middleware import geth_poa_middleware

import sha3
from ecdsa import SigningKey, SECP256k1

import logging
logger = logging.getLogger('autoranker')

from autoranker import Autoranker


def get_config(args):
    config = {
        "eth_http_node": "https://rinkeby.infura.io/v3/1474ceef2da44edbac41a2efd66ee882",
        # "eth_http_node": "http://10.100.11.24:8545",
        # "tcrank_address": "0x92dd1421d51f7a95eb7fd59634cb0082a0999c9a",
        # "faucet_address": "0x1a41d0442b0e90eb4723efbaecd1da6bb39c86a5",
        
        "tcrank_address": "0xf41bf51e450e67fc201bcc4e5176beffa7f7ccb1",
        "faucet_address": "0xa0033f1dfaf979c7b805041b528a4d0af73c2d25",
    }

    with open("../../solidity/smartz/ranking.abi") as json_data:
        config['tcrank_abi'] = json.load(json_data)

    if (args.keys_file):
        config['keys_file'] = args.keys_file.name
        config['accounts'] = json.load(args.keys_file)

    return config

def generate_keypair_and_address():                                                                                                                              
    priv = SigningKey.generate(curve=SECP256k1)                                                                                                                      
    pub = priv.get_verifying_key().to_string()                                                                                                                       
    keccak = sha3.keccak_256()                                                                                                                                       
    keccak.update(pub)  
    addr_str = keccak.hexdigest()[24:]
    out = ''
    addr = addr_str.lower().replace('0x', '')
    keccak.update(addr.encode('ascii'))
    hash_addr = keccak.hexdigest()
    for i, c in enumerate(addr):
        if int(hash_addr[i], 16) >= 8:
            out += c.upper()
        else:
            out += c
    address = '0x' + out
    return {'private_key': priv.to_string().hex(), 'public_key': pub.hex(), 'address': address}             

def main(arguments):

    logger = logging.getLogger('autoranker')
    fh = logging.FileHandler('/tmp/autoranker.log')
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
    fh.setFormatter(formatter)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-k', '--keys-file', help="File with keys and addresses", type=argparse.FileType('r'))
    parser.add_argument('--random-play', action="store_true", help="begins to push dapps randomly")
    parser.add_argument('--generate-keys-pack', action="store_true", help="outputs pack of keypairs + eth addresses")
    parser.add_argument('--dapp-id', action="store", type=int, help="performs operation for selected dapp id")
    parser.add_argument('--sync-dapps', action="store_true", help="begins to renew dapps in contract(if owner)")

    args = parser.parse_args(arguments)
    
    # GENERATES ARRAY OF DICTS with private,public keys and addresses
    if (args.generate_keys_pack == True):
        keys = []
        n = 0
        while (n < 7):
            keys.append(generate_keypair_and_address())
            n += 1
        print(json.dumps(keys, indent=4, sort_keys=True))
        return

    config = get_config(args)
    
    
    their_dapps = {}
    with open("./dapps.json") as f:
        their_dapps = json.load(f)

    # temp
    dapps = {}
    for id in their_dapps:
        dapps[id] = { 'id': id,
                     'name': their_dapps[id],
                     'rank': '1'
                    }

    # now create autoranker object and pass contract and account to it. Any further logic must be implemented in Autoranker class
    autoranker = Autoranker(config, dapps)
    
    if (args.sync_dapps == True):
        autoranker.load_dapps_to_contract()
        return

    if (args.random_play == True):
        single_dapp_id = args.dapp_id
        autoranker.start_moving_dapps(single_dapp_id)
        return

    print("Do nothing...")



def to_32byte_hex(val):
    return Web3.toHex(Web3.toBytes(val).rjust(32, b'\0'))



if __name__ == '__main__':
    start = time.time()
    sys.exit(main(sys.argv[1:]))

