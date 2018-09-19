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


def get_config():
    config = {
        "eth_http_node": "https://rinkeby.infura.io/v3/1474ceef2da44edbac41a2efd66ee882",
        "tcrank_address": "0xc28ab7c92be1c10ca0b06f84985be6114d4d450d",
        "faucet_address": "0xe56919582ec032575e70075bf374b227423de674",
    }
    with open("./tcrank.abi.json") as json_data:
        config['tcrank_abi'] = json.load(json_data)
    return config


def main(arguments):

    logger = logging.getLogger('autoranker')
    fh = logging.FileHandler('/tmp/autoranker.log')
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
    fh.setFormatter(formatter)


    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-k', '--private-key-file', required=True, help="File with private key", type=argparse.FileType('r'))
    args = parser.parse_args(arguments)
    private_key = args.private_key_file.read().strip()
    
    config = get_config()

    # now create autoranker object and pass contract and account to it. Any further logic must be implemented in Autoranker class
    autoranker = Autoranker(config, private_key)
    autoranker.load_dapps_info_to_contract()




def to_32byte_hex(val):
    return Web3.toHex(Web3.toBytes(val).rjust(32, b'\0'))



if __name__ == '__main__':
    start = time.time()
    sys.exit(main(sys.argv[1:]))

