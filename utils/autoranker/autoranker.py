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
import time

import hashlib
import os.path

import web3
from web3 import Web3, HTTPProvider, TestRPCProvider
from web3.contract import ConciseContract
from web3.middleware import geth_poa_middleware
from web3.exceptions import BadFunctionCallOutput
from eth_abi import encode_abi, decode_abi

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
        # enum ItemState { None, Voting }
        self.item_states = {0: 'none', 1: 'voting'}
        # enum VotingState { Commiting, Revealing, Finished }
        self.voting_states = { 0: 'commiting', 1: 'revealing', 2: 'finished' }
        logger.debug("Autoranker ready, address: {}, eth_balance: {}, CRN balance: {}"
                     .format(self.address, self.web3.fromWei(self.eth_balance, 'ether'), self.web3.fromWei(self.crn_balance, 'ether')))

        self.play_state = {
            'up_probability': 0.5, # probability to push item up or dawn
            'max_push_stake': 5, # max voting power for pushing item
            'accumulator': { 'simple_profit': 0,
                           }
        }


    def get_dapp_from_contract(self, dapp_id):
        dapp = {}
        
        try:
            dapp = self.tcrank.functions.getItem(self.to_uint256(dapp_id)).call()
        except web3.exceptions.BadFunctionCallOutput:
            # returned b''
            return None
        except Exception as e:
            print("Error getting dapp info from contract {}: {}".format(dapp_id, repr(e)))
            return None

        if self.dapps.get(dapp_id) is None:
            print("Dapp {} is no present in local dapps, creating new".format(dapp_id))
            self.dapps[dapp_id] = {'id': dapp_id, 'address': dapp[0], 'rank': dapp[1], 'balance': dapp[2], 'voting_id': dapp[3], 'movings_ids': dapp[3]}
        else:
            self.dapps[dapp_id]['address'] = dapp[0]
            self.dapps[dapp_id]['rank'] = dapp[1]
            self.dapps[dapp_id]['balance'] = dapp[2]
            self.dapps[dapp_id]['voting_id'] = dapp[3]
            self.dapps[dapp_id]['movings_ids'] = dapp[4]
        
        item_state_id = self.tcrank.functions.getItemState(self.to_uint256(dapp_id)).call()
        self.dapps[dapp_id]['item_state'] = self.item_states[item_state_id]

        voting_id = dapp[3]
        if (voting_id != 0):
            self.dapps[dapp_id]['voting'] = self.tcrank.functions.getVoting(voting_id).call()
            voting_state_id = self.tcrank.functions.getVotingState(voting_id).call()
            self.dapps[dapp_id]['voting_state'] = self.voting_states[voting_state_id]

        print("Working dapp:\n{}".format(json.dumps(self.dapps[dapp_id], sort_keys=True, indent=4)))
        return self.dapps[dapp_id]


    def push_selected_dapp(self, dapp_id, impulse):
        
        dapp = self.get_dapp_from_contract(dapp_id)
        
        current_ts = int(time.time())


        # KOSTYL!
        voting_commit_ttl = 180
        voting_reveal_ttl = 180
        voting_start_ts = current_ts - 10
        if (dapp.get('voting') is not None):
            voting_commit_ttl = dapp['voting'][2]
            voting_reveal_ttl = dapp['voting'][3]
            voting_start_ts = dapp['voting'][4]

        if (current_ts < voting_start_ts):
            print("Current time {} is before voting start {}: strange".format(current_ts, voting_start_ts))
            return None
        
        #elif (current_ts >= (voting_start_ts + voting_commit_ttl + voting_reveal_ttl)):
        #    print("Current time {} is too late for voting, deadline is {} ({} sec ago)"
        #          .format(current_ts, 
        #                  voting_start_ts + voting_commit_ttl + voting_reveal_ttl,
        #                  current_ts - voting_start_ts - voting_commit_ttl - voting_reveal_ttl))
        #    return None

        # we're in commit or reveal phase
        # TEMP (to ease reveal phase)
        impulse = int((int(dapp_id) % 10) - (int(dapp_id) % 10) / 2)

        isup = 0
        push_force = 1
        if (impulse >= 0):
            isup = 1
            push_force = impulse
        else:
            push_force = -1 * impulse
        
        salt = int(random.randint(0,100000000)) # FIXME
            
        # if we can commit to voting
        need_to_commit = False
        if (current_ts > voting_start_ts and current_ts < voting_start_ts + voting_commit_ttl):
            print("Current time {} is in commit phase ({} secs left), need to commit".format(current_ts, voting_start_ts + voting_commit_ttl - current_ts))
            need_to_commit = True
        elif (current_ts > voting_start_ts + voting_commit_ttl + voting_reveal_ttl):
            print("Current time {} is after finished voting ({} secs ago), we need to finishVoting first".format(current_ts, current_ts - voting_start_ts - voting_commit_ttl - voting_reveal_ttl))
            tx = self.tcrank.functions.finishVoting(self.to_uint256(dapp['id']))\
                                       .buildTransaction({
                                                            'gas': 7300000,
                                                            'gasPrice': self.web3.toWei('2', 'gwei'),
                                                            'nonce': self.web3.eth.getTransactionCount(self.address)
                                                        })
            signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
            print("Transaction finishVoting() sent, waiting for it...")
            self.web3.eth.waitForTransactionReceipt(tx_hash)
            print("Transaction finishVoting() done")
            need_to_commit = True

        # need_to_commit = False
        # print("stop!!!!")
        if (not need_to_commit):
            print("No need to commit")
            return False

        print("Plan to commitVote on dapp {}, salt: {}, isup: {}, push_force: {}".format(dapp_id, salt, isup, push_force))
        try:
            commit_hash = self.web3.soliditySha3(['uint256','uint256', 'uint256'], [ isup, push_force, salt])
            tx = self.tcrank.functions.voteCommit(self.to_uint256(dapp['id']), commit_hash)\
                                       .buildTransaction({
                                                            'gas': 5000000,
                                                            'gasPrice': self.web3.toWei('3', 'gwei'),
                                                            'nonce': self.web3.eth.getTransactionCount(self.address)
                                                        })
            signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
            print("Transaction voteCommit() sent, waiting for it...")
            self.web3.eth.waitForTransactionReceipt(tx_hash)

            print("Transaction voteCommit() done")
        except Exception as e:
            logger.error("Error calling voteCommit() function: {}".format(repr(e)))
        
        current_ts = int(time.time())
        if (current_ts < voting_start_ts + voting_commit_ttl):
            sleep_ts = 180 #voting_start_ts + voting_commit_ttl - current_ts
            print("Sleeping until reveal phase begins, plan to wait {} seconds".format(sleep_ts))
            time.sleep(sleep_ts)
            dapp = self.get_dapp_from_contract(dapp_id)

            try:
                commit_hash = self.web3.soliditySha3(['uint256','uint256', 'uint256'], [ isup, push_force, salt])
                tx = self.tcrank.functions.voteReveal(self.to_uint256(dapp['id']),
                                                      self.to_uint256(isup),
                                                      self.to_uint256(push_force),
                                                      self.to_uint256(salt))\
                                           .buildTransaction({
                                                                'gas': 5000000,
                                                                'gasPrice': self.web3.toWei('3', 'gwei'),
                                                                'nonce': self.web3.eth.getTransactionCount(self.address)
                                                            })
                signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
                tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
                logger.debug("Transaction voteReveal() sent, waiting for it...")
                self.web3.eth.waitForTransactionReceipt(tx_hash)
                logger.debug("Transaction voteReveal() done")
            except Exception as e:
                logger.error("Error calling voteReveal() function: {}".format(repr(e)))
                return False
 
        return True



    def start_moving_dapps(self):
        n = 0
        chosen_dapps = ["1164", "1163", "1162"]

        chosen_id = random.choice(chosen_dapps)
        chosen_id = "1163"
        # updates current state on disk
        impulse = int(self.play_state['max_push_stake'] * random.uniform(0, 1)) - int(self.play_state['max_push_stake'] / 2)
        # logger.debug("generated impulse: {}".format(impulse))
        
        dapp = self.get_dapp_from_contract(chosen_id)
        
        if (dapp.get('voting_state') is None):
            print("voting state is none, begin commiting")
            self.push_selected_dapp(chosen_id, impulse)
        elif (dapp['voting_state'] == 'commiting'): 
            print("voting state is 'commiting', begin commit")
            self.push_selected_dapp(chosen_id, impulse)
        elif (dapp['voting_state'] == 'revealing'):
            print("voting state is 'revealing', do nothing")
        elif (dapp['voting_state'] == 'finished'):
            print("voting state is 'finished', push another time")
            self.push_selected_dapp(chosen_id, impulse)
        
   


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
            if (int(self.dapps[dapp_id]['rank']) != int(new_rank)):
                print("Dapp {} is moving, rank changed {} -> {}, updating state".format(id, self.dapps[dapp_id]['rank'], new_rank))
                self.dapps[dapp_id]['rank'] = new_rank
            else:
                # print("Dapp {} rank is not changed, rank: {}".format(id, new_rank))
                pass


        return None



    def load_dapps_to_contract(self):
        PACKSIZE = 30
        ids_pack = []
        ranks_pack = []
        i = 0
        for dapp_id in self.dapps:
            dapp = self.dapps[dapp_id]
            existing = self.get_dapp_from_contract(dapp_id)
            if existing is not None:
                logger.info("Dapp [{}] {}, already exists in contract, continue".format(dapp_id, dapp))
                continue

            i += 1
            if ((i % PACKSIZE) != 0 and i < len(self.dapps)) != 0:
                ids_pack.append(self.to_uint256(dapp_id))
                ranks_pack.append(self.to_uint256(dapp['rank']))
                continue

            # pack are full, push them
            logger.info("Dapps ({}) adding to contract with ranks({})".format(', '.join(str(x) for x in ids_pack), ', '.join(str(x) for x in ranks_pack)))
            tx = self.tcrank.functions.newItemsWithRanks(_ids=ids_pack,
                                                         _ranks=ranks_pack).buildTransaction({
        						'gas': 6000000,
        						'gasPrice': self.web3.toWei('1', 'gwei'),
                                                        'nonce': self.web3.eth.getTransactionCount(self.address)
                                                        })
            signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
            logger.debug("Transaction send, sleeping")
            time.sleep(120)
            # self.web3.eth.waitForTransactionReceipt(tx_hash)
            ids_pack = []
            ranks_pack = []

        return None

    def push_tcrank_item(self, dapp_id, impulse):
        pass
