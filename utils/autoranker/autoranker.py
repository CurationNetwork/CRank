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

    # convert to uint256
    def to_uint256(self, number):
        return self.web3.toWei(str(number), 'wei')


    def __init__(self, config, private_key):
        self.config = config
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

    
    def get_dapp_from_contract(self, dapp_id):
        try: 
            r = self.tcrank.functions.getItem(self.to_uint256(dapp_id)).call()
            return r
        except Exception as e:
            print("Dapp with id: {} doesn't exist in contract".format(dapp_id))
        
        return None
 
    def get_dapps_from_contract(self, dapps):
        their_dapps = {}
        for dapp_id in dapps:
            dapp = dapps[dapp_id]
            try: 
                r = self.tcrank.functions.getItem(self.to_uint256(dapp_id)).call()
            except Exception as e:
                print("Dapp with id: {} doesn't exist in contract".format(dapp_id))
                continue
        
    def load_dapps_info_to_contract(self, dapps):
        for dapp_id in dapps:
            dapp = dapps[dapp_id]
            existing = self.get_dapp_from_contract(dapp_id)
            if existing is not None:
                logger.debug("Dapp [{}] {}, already exists in contract, continue".format(dapp_id, dapp))
                continue

            dapp = dapps[dapp_id]
            # est_gaz = self.tcrank.functions.newItemWithRank(self.to_uint256(dapp_id), dapp_our_rank).estimateGas()
            tx = self.tcrank.functions.newItemWithRank(_id=self.to_uint256(dapp_id), 
                                                       _rank=self.to_uint256(1)).buildTransaction({
        						'gas': 1400000,
        						'gasPrice': self.web3.toWei('10', 'gwei'),
                                                        'nonce': self.web3.eth.getTransactionCount(self.address)
                                                        })
            signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction) 
            self.web3.eth.waitForTransactionReceipt(tx_hash)
            logger.info("Dapp [{}] {}, added to contract".format(dapp_id, dapp))
        
        return None

    def push_tcrank_item(self, dapp_id, impulse):
        pass
