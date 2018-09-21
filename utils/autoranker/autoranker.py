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
import random

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


    def __init__(self, config, private_key, dapps):
        self.config = config
        self.dapps = dapps
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
        self.eth_balance = self.web3.eth.getBalance(self.address)
        self.crn_balance = self.tcrank.functions.balanceOf(self.address).call()
        logger.debug("Autoranker ready, address: {}, eth_balance: {}, CRN balance: {}"
                     .format(self.address, self.web3.fromWei(self.eth_balance, 'ether'), self.web3.fromWei(self.crn_balance, 'ether'))) 

        self.play_state = {
            'up_probability': 0.5, # probability to push item up or dawn
            'max_push_stake': 100, # max voting power for pushing item
            'accumulator': { 'simple_profit': 0,
                           }
        }


    def get_dapp_from_contract(self, dapp_id):
        try: 
            r = self.tcrank.functions.getItem(self.to_uint256(dapp_id)).call()
            return r
        except Exception as e:
            print("Dapp with id: {} doesn't exist in contract".format(dapp_id))
        
        return None
 
    def start_moving_dapps(self):
        n = 0 
        while (n < 3):
            n += 1
            self.update_ranks_from_contract()
            in_contract_dapps = []
            for dapp_id in self.dapps:
                if self.dapps[dapp_id].get('sync') == True:
                    in_contract_dapps.append(dapp_id)
                
            chosen_id = random.choice(in_contract_dapps)
            
            isup = False
            if (random.uniform(0, 1) > self.play_state['up_probability']):
                isup = True
            push_force = int(self.play_state['max_push_stake'] * random.uniform(0, 1))
            print("Plan to push Dapp [{}], up: {}, force {}".format(chosen_id, isup, push_force))





            time.sleep(0.0001)


    def update_ranks_from_contract(self):
        ranks = None
        try: 
            ranks = self.tcrank.functions.getItemsWithRank().call()
        except Exception as e:
            logger.error("Error calling getItemsWithRank() function: {}".format(repr(e)))
            raise
 
        for id, new_rank in zip(ranks[0], ranks[1]):
            dapp_id = str(id)
            if (self.dapps.get(dapp_id) is None):
                # print("Dapp {} with rank {} not exists in self.dapps - contract and local dapps not sync".format(dapp_id, new_rank))
                self.dapps[dapp_id]['sync'] = False
                continue
            self.dapps[dapp_id]['sync'] = True
            if (self.dapps[dapp_id]['rank'] != new_rank):
                print("Dapp {} is moving, rank changed {} -> {}, updating state", format(id, self.dapps[dapp_id]['rank'], new_rank))
                self.dapps[dapp_id]['rank'] = new_rank
            else:
                # print("Dapp {} rank is not changed, rank: {}".format(id, new_rank))
                pass
       
        return None

               
 
    def load_dapps_to_contract(self):
        for dapp_id in self.dapps:
            dapp = self.dapps[dapp_id]
            existing = self.get_dapp_from_contract(dapp_id)
            if existing is not None:
                logger.debug("Dapp [{}] {}, already exists in contract, continue".format(dapp_id, dapp))
                continue

            tx = self.tcrank.functions.newItemWithRank(_id=self.to_uint256(dapp_id), 
                                                       _rank=self.to_uint256(dapp.rank)).buildTransaction({
        						'gas': 1400000,
        						'gasPrice': self.web3.toWei('1', 'gwei'),
                                                        'nonce': self.web3.eth.getTransactionCount(self.address)
                                                        })
            signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction) 
            self.web3.eth.waitForTransactionReceipt(tx_hash)
            logger.info("Dapp [{}] {}, added to contract".format(dapp_id, dapp))
        
        return None

    def push_tcrank_item(self, dapp_id, impulse):
        pass
