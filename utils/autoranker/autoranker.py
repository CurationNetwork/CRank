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

class Autoranker(object):

    def __init__(self, config, private_key):
        self.web3 = Web3(Web3.HTTPProvider(config['eth_http_node']))
        # need for Rinkeby network
        self.web3.middleware_stack.inject(geth_poa_middleware, layer=0)
        if (not self.web3.isConnected()):
            raise Exception("[ERROR] Web3 is not connected to {}: {}".format(config['eth_http_node'], self.web3))

        logger.debug("Connected to node, provider: {}".format(config['eth_http_node']))
        self.private_key = private_key
        keccak = sha3.keccak_256()
        sk = SigningKey.from_string(bytes().fromhex(private_key), curve=SECP256k1)
        self.public_key = sk.get_verifying_key().to_string()
        keccak.update(self.public_key)
        self.address = self.web3.toChecksumAddress("0x{}".format(keccak.hexdigest()[24:]))
        self.tcrank = self.web3.eth.contract(address=self.web3.toChecksumAddress(config['tcrank_address']), abi=config['tcrank_abi'])

    def load_dapps_info_to_contract(self):
        balance_wei = self.tcrank.functions.balanceOf(self.address).call()
        balance = Web3.fromWei(balance_wei, 'ether')
        logger.debug("Init account, all transactions will be fired from address: {}, token's balance: {}".format(self.address, balance))

