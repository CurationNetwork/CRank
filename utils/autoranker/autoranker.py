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
import sys

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

    def __init__(self, config, dapps):
        self.config = config
        self.dapps = dapps
        self.web3 = Web3(Web3.HTTPProvider(config['eth_http_node']))
        # need for Rinkeby network
        self.web3.middleware_stack.inject(geth_poa_middleware, layer=0)
        if (not self.web3.isConnected()):
            raise Exception("[ERROR] Web3 is not connected to {}: {}".format(config['eth_http_node'], self.web3))

        logger.debug("Connected to node, provider: {}".format(config['eth_http_node']))
        if (not config.get('accounts')):
            raise Exception("[ERROR] Accounts was not loaded from file '{}'".format(config['keys_file']))
        
        self.private_key = self.config['accounts'][0]['private_key']
        sk = SigningKey.from_string(bytes().fromhex(self.private_key), curve=SECP256k1)
        self.public_key = self.config['accounts'][0]['public_key']
        self.address = self.web3.toChecksumAddress(self.config['accounts'][0]['address'])
        
        self.tcrank = self.web3.eth.contract(address=self.web3.toChecksumAddress(config['tcrank_address']), abi=config['tcrank_abi'])

        self.eth_balance = self.web3.eth.getBalance(self.address)
        self.crn_balance = self.tcrank.functions.balanceOf(self.address).call()
        # enum ItemState { None, Voting }
        self.item_states = {0: 'none', 1: 'voting'}
        # enum VotingState { Commiting, Revealing, Finished }
        self.voting_states = { 0: 'commiting', 1: 'revealing', 2: 'finished' }
        logger.debug("Autoranker ready, address: {}, eth_balance: {}, CRN balance: {}"
                     .format(self.address, self.web3.fromWei(self.eth_balance, 'ether'), self.web3.fromWei(self.crn_balance, 'ether')))

        self.play_params = {
            'up_probability': 0.9, # probability to push item up or dawn
            'max_push_stake': 20, # max voting power for pushing item
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
            print("DApp [{}] is not present in local dapps, creating new".format(dapp_id))
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

        # print("Working dapp:\n{}".format(json.dumps(self.dapps[dapp_id], sort_keys=True, indent=4)))
        return self.dapps[dapp_id]


    def get_random_push_params(self, dapp_id, current_ts):
        # generate same push params for same dapp_id in range of two minutes minute (to reconstruct reveal info)
        seed_str = str(dapp_id) + '_' + str(current_ts - (current_ts % 30))
        # random.seed(seed_str)
        impulse = int(self.play_params['max_push_stake'] * random.uniform(0, 1)) - int(self.play_params['max_push_stake'] / 2)
        salt = int(random.randint(0,100000000)) # FIXME

        isup = 0
        push_force = 1
        # leave push_force == 1 if impulse == 0
        if (impulse > 0):
            isup = 1
            push_force = impulse
        elif (impulse < 0):
            push_force = -1 * impulse
        
        commit_hash = self.web3.soliditySha3(['uint256','uint256', 'uint256'], [ isup, push_force, salt])
        
        account = random.choice(self.config['accounts'])
        
        return {'account': account,  'isup': isup, 'push_force': push_force, 'impulse': impulse, 'salt': salt, 'commit_hash': commit_hash, 'seed_str': seed_str }
        
    

    def push_selected_dapp(self, dapp_id):
        
        actions = []
        
        dapp = self.get_dapp_from_contract(dapp_id)
        current_ts = int(time.time())
        # get random params for push - impulse, random salt, calculate commit hash
        push_params = self.get_random_push_params(dapp['id'], current_ts)        
        acc = push_params['account']

        acc['eth_balance'] = self.web3.eth.getBalance(acc.address)
        acc['crn_balance'] = self.tcrank.functions.balanceOf(acc.address).call()

        if acc['eth_balance'] == 0:
            actions.append({'action': 'giveEther',
                                'params': [{'from': self.config['accounts'][0]['address'], 'amount': 0.3}],
                                'wait': 30});

        if acc['crn_balance'] == 0:
            actions.append({'action': 'faucetTokens',
                                'params': [],
                                'wait': 30});



        commit_ttl = 30
        reveal_ttl = 30
        voting_active = False

        if (dapp.get('voting') is not None):
            commit_ttl = dapp['voting'][2]
            reveal_ttl = dapp['voting'][3]
            start_ts = dapp['voting'][4]
            voting_active = True
        
        if (dapp.get('voting_state') == 'finished'):
            voting_active = False

        # plan actions for 4 phases
        # -----1(before voting start)---|---2(commit phase)----|---3(reveal_phase)----|----4(finish voting allowed)---------

        if (not voting_active):
            print("DApp [{}], rank: {}, current time {}, no active voting, plan full cycle"
                  .format(dapp_id, dapp.get('rank'), current_ts))
            actions.append({'action': 'voteCommit',
                            'params': [self.to_uint256(dapp['id']), push_params['commit_hash']],
                            'wait': commit_ttl}); # FIXME - calculate
            actions.append({'action': 'voteReveal',
                            'params': [self.to_uint256(dapp['id']),                                                                                       
                                       self.to_uint256(push_params['isup']),                                                                                             
                                       self.to_uint256(push_params['push_force']),                                                                                       
                                       self.to_uint256(push_params['salt'])],
                            'wait': reveal_ttl}); # FIXME - calculate

            actions.append({'action': 'finishVoting',
                            'params': [self.to_uint256(dapp['id'])],
                            'wait': 0}); # FIXME - calculate
            
            print("DApp [{}], plan to push with impulse: {}, seed: {}".format(dapp['id'], push_params['impulse'], push_params['seed_str']))
        else:
            ########### ERROR #########################
            if (current_ts < start_ts): 
                print("DApp [{}], rank: {}, voting exists, but start time in in future, current ts: {}, voting starts at {} ({} secs after). Do nothing"
                             .format(dapp['id'], dapp.get('rank'), current_ts, start_ts, start_ts - current_ts))
            ######### COMMIT PHASE ##################
            elif (current_ts >= start_ts and current_ts <= (start_ts + commit_ttl)):
                seconds_left = start_ts + commit_ttl - current_ts
                print("DApp [{}], current time {} is in commit phase ({} secs left), plan full cycle"
                      .format(dapp_id, current_ts, seconds_left))

                actions.append({'action': 'voteCommit',
                                'params': [self.to_uint256(dapp['id']), push_params['commit_hash']],
                                'wait': seconds_left});
                actions.append({'action': 'voteReveal',
                                'params': [self.to_uint256(dapp['id']),                                                                                       
                                           self.to_uint256(push_params['isup']),                                                                                             
                                           self.to_uint256(push_params['push_force']),                                                                                       
                                           self.to_uint256(push_params['salt'])],
                                'wait': reveal_ttl}); # FIXME - calculate

                actions.append({'action': 'finishVoting',
                                'params': [self.to_uint256(dapp['id'])],
                                'wait': 0});

            ############ REVEAL PHASE ##################
            elif (current_ts >= (start_ts + commit_ttl) and current_ts <= (start_ts + commit_ttl + reveal_ttl)):
                seconds_left = start_ts + commit_ttl + reveal_ttl - current_ts
                print("DApp [{}], current time {} is in reveal phase ({} secs left), plan reveal cycle"
                      .format(dapp_id, current_ts, seconds_left))
                actions.append({'action': 'voteReveal',
                                'params': [self.to_uint256(dapp['id']),                                                                                       
                                           self.to_uint256(push_params['isup']),                                                                                             
                                           self.to_uint256(push_params['push_force']),                                                                                       
                                           self.to_uint256(push_params['salt'])],
                                'wait': seconds_left });

                actions.append({'action': 'finishVoting',
                                'params': [self.to_uint256(dapp['id'])],
                                'wait': 0});
            ############### FINISH PHASE #################
            elif (current_ts > (start_ts + commit_ttl + reveal_ttl)):
                print("DApp [{}], current time {} is after finished voting ({} secs ago), plan finish voting"
                      .format(dapp_id, current_ts, current_ts - start_ts - commit_ttl - reveal_ttl))
                actions.append({'action': 'finishVoting',
                                'params': [self.to_uint256(dapp['id'])],
                                'wait': 0});

        print("CUT!")
        return

        ################## ACTIONS READY ########################
        for a in actions:
            dapp = self.get_dapp_from_contract(dapp_id)
            print("DApp [{}], performing '{}' action".format(dapp['id'], a['action']))
            args = a.get('params', [])
            tx = None

            if (a['action'] == 'giveEther'):
                params = args[0] # passed as "{ from: '0x....', amount: 0.3 }"
                transaction = {
                    'to': params['from'],
                    'value': self.web3.toWei(params['amount'], 'ether'),
                    'gas': 2000000,
                    'gasPrice': self.web3.toWei('1.5', 'gwei'),
                    'nonce': self.web3.eth.getTransactionCount(self.address),
                }


            print("CUT!!!!!!!!!!")
            continue

            if (a['action'] == 'voteCommit'):
                tx = self.tcrank.functions.voteCommit(*args)\
                                               .buildTransaction({
                                                                    'gas': 3000000,
                                                                    'gasPrice': self.web3.toWei('1', 'gwei'),
                                                                    'nonce': self.web3.eth.getTransactionCount(self.address)
                                                                })

            elif (a['action'] == 'voteReveal'):
                tx = self.tcrank.functions.voteReveal(*args)\
                                               .buildTransaction({
                                                                    'gas': 4000000,
                                                                    'gasPrice': self.web3.toWei('1', 'gwei'),
                                                                    'nonce': self.web3.eth.getTransactionCount(self.address)
                                                                })

            elif (a['action'] == 'finishVoting'):
                tx = self.tcrank.functions.finishVoting(*args)\
                                               .buildTransaction({
                                                                    'gas': 7300000,
                                                                    'gasPrice': self.web3.toWei('3', 'gwei'),
                                                                    'nonce': self.web3.eth.getTransactionCount(self.address)
                                                                })

            else:
                print("DApp [{}]. Error: unknown action '{}'".format(dapp['id'], a['action']))
                continue

            tx_hash = None
            try:
                signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
                a['tx_hash'] = self.web3.toHex(signed_tx.get('hash'))
                tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
                print("DApp [{}], transaction {}() sent, waiting. tx_hash: {}".format(dapp['id'], a['action'], a['tx_hash']))
                self.web3.eth.waitForTransactionReceipt(tx_hash)
                print("DApp [{}], transaction {}() done, tx_hash: {}".format(dapp['id'], a['action'], a['tx_hash']))
                a['completed'] = True
            except ValueError as e:
                print("DApp [{}], transaction {}(), exception: {}".format(dapp['id'], a['action'], repr(e)))
                if (str(e.args[0]['code']) == '-32000'): # already processing tx
                    print("DApp [{}], transaction {}() is active, tx_hash: {}".format(dapp['id'], a['action'], a['tx_hash']))
                    try:
                        self.web3.eth.waitForTransactionReceipt(a['tx_hash'])
                        a['completed'] = True
                    except Exception as e:
                        print("DApp [{}], error calling {}() function: {}".format(dapp['id'], a['action'], repr(e)))
                        
            except Exception as e:
                print("DApp [{}], error calling {}() function: {}".format(dapp['id'], a['action'], repr(e)))
              
            
            if a.get('completed') is None:
                print("DApp [{}], error, transaction was not executed, breakin action queue".format(dapp['id']))
                break

            print("DApp [{}], sleeping {} sec (taken from 'wait' action parameter)".format(dapp['id'], a['wait']))
            time.sleep(a['wait'])

        return True



    def start_moving_dapps(self, single_dapp_id, n_dapps=50):
        print("Start to play, play_params: {}".format(repr(self.play_params)))
        n = 0

        if (single_dapp_id):
            self.push_selected_dapp(single_dapp_id)
            return


        chosen_dapps = []
        for dapp_id in self.dapps:
            if (int(dapp_id) % 33 == 0):
                chosen_dapps.append(dapp_id)

        while n < n_dapps:
            n += 1
            chosen_id = random.choice(chosen_dapps)
            self.push_selected_dapp(chosen_id)


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
                # print("DApp [{}] with rank {} not exists in self.dapps - contract and local dapps not sync".format(dapp_id, new_rank))
                self.dapps[dapp_id]['sync'] = False
                continue
            self.dapps[dapp_id]['sync'] = True
            if (int(self.dapps[dapp_id]['rank']) != int(new_rank)):
                print("DApp [{}] is moving, rank changed {} -> {}, updating state".format(id, self.dapps[dapp_id]['rank'], new_rank))
                self.dapps[dapp_id]['rank'] = new_rank
            else:
                # print("DApp [{}] rank is not changed, rank: {}".format(id, new_rank))
                pass


        return None



    def load_dapps_to_contract(self):
        PACKSIZE = 32
        ids_pack = []
        ranks_pack = []
        i = 0
        for dapp_id in self.dapps:
            dapp = self.dapps[dapp_id]
            #if (int(dapp_id) > 100):
            #    continue

            existing = self.get_dapp_from_contract(dapp_id)
            if existing is not None:
                logger.info("DApp [{}] {}, already exists in contract, continue".format(dapp_id, dapp))
                continue

            i += 1
            if ((i % PACKSIZE) != 0 and i < len(self.dapps)) != 0:
                ids_pack.append(self.to_uint256(dapp_id))
                ranks_pack.append(self.to_uint256(dapp['rank']))
                continue

            # pack are full, push them
            logger.info("DApps ({}) adding to contract with ranks({})".format(', '.join(str(x) for x in ids_pack), ', '.join(str(x) for x in ranks_pack)))
            tx = self.tcrank.functions.newItemsWithRanks(_ids=ids_pack,
                                                         _ranks=ranks_pack).buildTransaction({
        						'gas': 5000000,
        						'gasPrice': self.web3.toWei('2', 'gwei'),
                                                        'nonce': self.web3.eth.getTransactionCount(self.address)
                                                        })
            signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
            self.web3.eth.waitForTransactionReceipt(tx_hash)
            logger.debug("Transaction sent, sleeping")
            time.sleep(20)
            ids_pack = []
            ranks_pack = []

        return None
