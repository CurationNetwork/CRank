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
import datetime
import hashlib
import os.path
import sys

import web3
from web3 import Web3, HTTPProvider, TestRPCProvider
from web3.contract import ConciseContract
from web3.middleware import geth_poa_middleware
from web3.exceptions import BadFunctionCallOutput
from web3.utils.events import get_event_data
from eth_abi import encode_abi, decode_abi

import plotly
import plotly.graph_objs as go

import numpy as np

import sha3
from ecdsa import SigningKey, SECP256k1

import logging
logger = logging.getLogger('autoranker')


INIT_RANK = 300000000000000000000

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
        self.faucet = self.web3.eth.contract(address=self.web3.toChecksumAddress(config['faucet_address']), abi=config['faucet_abi'])

        self.eth_balance = self.web3.eth.getBalance(self.address)
        self.crn_balance = self.tcrank.functions.balanceOf(self.address).call()

        # enum ItemState { None, Voting }
        self.item_states = {0: 'none', 1: 'voting'}
        # enum VotingState { Commiting, Revealing, Finished }
        self.voting_states = { 0: 'commiting', 1: 'revealing', 2: 'finished' }
        logger.debug("Autoranker ready, address: {}, eth_balance: {}, CRN balance: {}"
                     .format(self.address, self.web3.fromWei(self.eth_balance, 'ether'), self.web3.fromWei(self.crn_balance, 'ether')))

        self.play_params = {
            'up_probability': 0.5, # probability to push item up or dawn
            'max_push_stake': 30, # max voting power for pushing item
            'accumulator': { 'simple_profit': 0,
                           }
        }

    def get_dapp_from_contract(self, dapp_id):
        result_dapp = {}
        
        try:
            dapp = self.tcrank.functions.getItem(self.to_uint256(dapp_id)).call()
        except web3.exceptions.BadFunctionCallOutput:
            # returned b''
            return None
        except Exception as e:
            print("Error getting dapp info from contract {}: {}".format(dapp_id, repr(e)))
            return None
        

        result_dapp['id'] = dapp_id
        result_dapp['address'] = dapp[0]
        result_dapp['rank'] = dapp[1]
        result_dapp['balance'] = dapp[2]
        result_dapp['voting_id'] = dapp[3]
        result_dapp['movings_ids'] = dapp[4]
    
        item_state_id = self.tcrank.functions.getItemState(self.to_uint256(dapp_id)).call()
        result_dapp['item_state'] = self.item_states[item_state_id]
        # ARRAY_JOPA (FIXME)
        voting_id = dapp[3]
        if (voting_id != 0):
            result_dapp['voting'] = self.tcrank.functions.getVoting(voting_id).call()
            voting_state_id = self.tcrank.functions.getVotingState(voting_id).call()
            result_dapp['voting_state'] = self.voting_states[voting_state_id]

        # print("Working dapp:\n{}".format(json.dumps(result_dapp, sort_keys=True, indent=4)))
        return result_dapp


    def show_ranking(self):
        ranking = {}
        stats = { 'total':0, 'dno': 0, 'moving':0, 'commit':0, 'reveal':0, 'unfinished':0 }
        res = [[],[]]
        try:
            res = self.tcrank.functions.getItemsWithRank().call()
        except BadFunctionCallOutput as e:
            print("Error calling getItemsWithRank(), nothing returned from contract at {}: {}".format(self.config['tcrank_address'], repr(e)))

        i = 0
        for (id, rank) in zip(res[0], res[1]):
            stats['total'] += 1
            # FIXME correctly UPDATE RANKS HERE (not actual beacuse of default INIT_RANK (I just skip this items), it's wrong
            if (rank == str(INIT_RANK)):
                stats['dno'] += 1
                continue


            if (self.dapps.get(str(id)) is None):
                # print("Dapp [{}] not found in self.dapps, strange".format(id))
                continue

            name = self.dapps[str(id)].get('name')
            dapp = {'rank': rank, 'name': name, 'info': 'idle'}

            dapp_item = self.tcrank.functions.getItem(self.to_uint256(id)).call()
            # ARRAY JOPA (FIXME)
            if (int(dapp_item[3]) != 0):
                v = self.tcrank.functions.getVoting(self.to_uint256(dapp_item[3])).call()
                # dapp['voting'] = v
                # [29517632169067660389, 1000000000000000000, 30, 30, 1538397188, 29517632169067660389, 296125441696112863068, ['0x6290C445A720E8E77dd8527694030028D1762073']]
                curts = time.time()
                # v[4] - start
                # v[2] - commit pahse length
                # v[3] - reveal phase length
    
                if (curts < v[4]):
                    dapp['info'] = "voting: not started yet(strange), {} sec left".format(int(v[4] - curts))
                elif (curts >= v[4] and curts < v[4] + v[2]):
                    dapp['info'] = "voting: commit phase, {} sec left".format(int(v[4] + v[2] - curts))
                elif (curts >= v[4] + v[2] and curts < v[4] + v[2] + v[3]):
                    dapp['info'] = "voting: reveal phase, {} sec left".format(int(v[4] + v[2] + v[3] - curts))
                elif (curts >= v[4] + v[2] + v[3]):
                    dapp['info'] = "voting: finish phase, {} sec waiting for finish".format(int(curts - (v[4] + v[2] + v[3])))

                  # aotin_id = dapp_item.get('votingId')
            # iaf (not voting_id):
                
            ranking[id] = dapp

        i = 0
        for dapp_id in sorted(ranking, key=lambda x: ranking[x]['rank'], reverse=True):
            d = ranking[dapp_id]
            print("{:>4}: DApp[{:>4}] {:>32},    rank(rounded): {:>7},    status: {}".format(i, dapp_id, d['name'], int(self.web3.fromWei(d['rank'], 'ether')), d['info']))
            i += 1
 
        # print(json.dumps(ranking, indent=4, sort_keys=True))
        # print(repr(stats))
        
    def get_random_push_params(self, dapp_id, current_ts):
        # generate same push params for same dapp_id in range of two minutes minute (to reconstruct reveal info)
        seed_str = str(dapp_id) + '_' + str(current_ts - (current_ts % 30))
        # random.seed(seed_str)
        impulse = int(self.play_params['max_push_stake'] * random.uniform(0, 1))
        salt = int(random.randint(0,100000000)) # FIXME

        isup = 0
        push_force = 1
        # leave push_force == 1 if impulse == 0
        if (random.uniform(0, 1) <= self.play_params['up_probability']):
            isup = 1
            push_force = impulse
        elif (impulse < 0):
            push_force = -1 * impulse
        
        push_force = self.web3.toWei(push_force, 'ether')

        commit_hash = self.web3.soliditySha3(['uint256','uint256', 'uint256'], [ isup, push_force, salt])
        
        account = random.choice(self.config['accounts'])
        # FIXME 
        account['address'] = self.web3.toChecksumAddress(account['address'])
        
        return {'account': account, 
                'isup': isup,
                'push_force': push_force,
                'impulse': impulse,
                'salt': salt,
                'commit_hash': commit_hash,
                'seed_str': seed_str }
        
    

    def push_selected_dapp(self, dapp_id):
        
        actions = []
        
        dapp = self.get_dapp_from_contract(dapp_id)
        current_ts = int(time.time())
        # get random params for push - impulse, random salt, calculate commit hash
        push_params = self.get_random_push_params(dapp['id'], current_ts)        
        acc = push_params['account']

        acc['eth_balance'] = self.web3.eth.getBalance(acc['address'])
        acc['crn_balance'] = self.tcrank.functions.balanceOf(acc['address']).call()
        print("Plan to use addr: {}, eth balance: {}, CRN balance: {}".format(acc['address'], self.web3.fromWei(acc['eth_balance'], 'ether'), self.web3.fromWei(acc['crn_balance'], 'ether')))
        faucet_addr = self.config['accounts'][0]['address']

        if acc['eth_balance'] == 0:
            eth_amount = 0.3
            faucet_addr = self.config['accounts'][0]['address']
            print("No ether on address {}, sending {} eth it from {}".format(acc['address'], faucet_addr, eth_amount))
            actions.append({'action': 'giveEther',
                                'params': [{'to': acc['address'], 'from': faucet_addr, 'amount': eth_amount}],
                                'wait': 3});

        if acc['crn_balance'] == 0:
            crn_amount = 100
            print("No CRN tokens on address {}, sending {} CRN from {}".format(acc['address'], faucet_addr, crn_amount))
            actions.append({'action': 'giveTokens',
                                'params': [{'to': acc['address'], 'from': faucet_addr, 'amount': crn_amount}],
                                'wait': 3});



        commit_ttl = 30
        reveal_ttl = 30
        voting_active = False

        if (dapp.get('voting') is not None):
            commit_ttl = dapp['voting'][2]
            reveal_ttl = dapp['voting'][3]
            start_ts = dapp['voting'][4]
            voting_active = True
        else:
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

        ################## ACTIONS READY ########################
        for a in actions:
            dapp = self.get_dapp_from_contract(dapp_id)
            print("DApp [{}], performing '{}' action".format(dapp['id'], a['action']))
            args = a.get('params', [])
            tx = None

            if (a['action'] == 'giveEther'):
                params = args[0] # passed as "{ from: '0x....', amount: 0.3 }"
                tx = {
                    'from': params['from'],
                    'to': params['to'],
                    'value': self.web3.toWei(params['amount'], 'ether'),
                    'gas': 1000000,
                    'gasPrice': self.web3.toWei('1.5', 'gwei'),
                    'nonce': self.web3.eth.getTransactionCount(self.address),
                }

            elif (a['action'] == 'giveTokens'):
                params = args[0] # passed as "{ from: '0x....', amount: 0.3 }"
                tx = self.tcrank.functions.transfer(params['to'], self.web3.toWei(params['amount'], 'ether'))\
                                               .buildTransaction({
                                                                    'gas': 1000000,
                                                                    'gasPrice': self.web3.toWei('1', 'gwei'),
                                                                    'nonce': self.web3.eth.getTransactionCount(self.address)
                                                                })
            elif (a['action'] == 'voteCommit'):
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



    def start_moving_dapps(self, single_dapp_id, n_dapps=1900):
        print("Start to play, play_params: {}".format(repr(self.play_params)))
        n = 0

        if (single_dapp_id):
            self.push_selected_dapp(single_dapp_id)
            return


        chosen_dapps = []
        for dapp_id in self.dapps:
            # if (int(dapp_id) % 17 == 0):
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



    def load_dapps_to_contract(self, single_dapp_id):
        PACKSIZE = 32
        
        ids_pack = []
        ranks_pack = []
        new_dapps_ids = []
        rank_updates = []
        for dapp_id in self.dapps:
            dapp = self.dapps[dapp_id]
            

            if single_dapp_id is not None:
                if str(single_dapp_id) != str(dapp_id):
                    continue
                
                print("Working with single dapp: [{}] {}".format(dapp_id, dapp.get('name')))

            existing = self.get_dapp_from_contract(dapp_id)
            if existing is not None:
                logger.info("DApp [{}] {}, already exists in contract with rank: {}, local rank: {}".format(dapp_id, dapp.get('name'), existing['rank'], dapp['rank']))
                if (str(dapp['rank']) != str(existing['rank'])):
                    logger.info("DApp [{}] {}, need to update rank from {} to {}".format(dapp_id, dapp.get('name'), existing['rank'], dapp['rank']))
                    rank_updates.append([dapp_id, dapp['rank'], existing['rank']])
                continue

            new_dapps_ids.append(dapp_id)

        i = 0
        for dapp_id in new_dapps_ids:
            i +=1
            ids_pack.append(self.to_uint256(dapp_id))
            ranks_pack.append(self.to_uint256(self.dapps[dapp_id]['rank']))

            if (i % PACKSIZE) != 0 and i < len(new_dapps_ids):
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
            logger.debug("Transaction 'newItemsWithRanks' sent, sleeping")
            time.sleep(30)
            ids_pack = []
            ranks_pack = []

        return None

        # update ranks for changed ranks
        for u in sorted(rank_updates, key = lambda r: r[1], reverse=True):
            
            dapp_id = u[0]
            new_rank = u[1]
            old_rank = u[2]
            logger.info("DApp [{}] {}, SKIIIPPP updating rank from {} to {}".format(dapp_id, self.dapps.get(dapp_id, {}).get('name'), old_rank, new_rank))
            continue
            tx = self.tcrank.functions.setItemLastRank(_itemId=self.to_uint256(dapp_id),
                                                       _rank=self.to_uint256(new_rank)).buildTransaction({
                                'gas': 3000000,
                                'gasPrice': self.web3.toWei('2', 'gwei'),
                                                        'nonce': self.web3.eth.getTransactionCount(self.address)
                                                         })
            signed_tx = self.web3.eth.account.signTransaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
            self.web3.eth.waitForTransactionReceipt(tx_hash)
            logger.debug("Transaction 'setItemLastRank' sent, sleeping")
            time.sleep(30)

        return None


    def tx_to_json(tx):
        result = {}
        for key, val in tx.items():
            if isinstance(val, HexBytes):
                result[key] = val.hex()
            else:
                result[key] = val

        return json.dumps(result)

 
    def mov_func_y_from_t(self, last_y, delta_t, speed, distance):
        moving_time = int(distance / speed)
        # print("dist: {}, speed: {}, delta_t: {}".format(distance, speed, delta_t))
        if delta_t <= moving_time:
            # print("{} -> {} (speed: {})".format(last_y, last_y + delta_t * speed, speed))
            return last_y + delta_t * speed
        return last_y + distance

        # movement equation when object is not pushed and stays without action for some interval of time
        # intertial_function = lambda delta_t, initial_speed, interval: 0



    def ranking_history(self, single_dapp_id, output_file):

        MOVING_EVENT_NAME = 'MovingStarted'

        event_abi = None
        for i in self.config['tcrank_abi']:
            if i['type'] == 'event' and i['name'] == MOVING_EVENT_NAME:
                event_abi = i
                break

        if event_abi is None:
            raise KeyError("No abi for event '{}' was found in ranking.abi".format(MOVING_EVENT_NAME))


        addr = self.web3.toChecksumAddress(self.config['tcrank_address'])
        event_signature = self.web3.sha3(text='MovingStarted(uint256,uint256,uint256,uint256,uint256,uint256,uint256)').hex()
        filt = self.web3.eth.filter({'address': addr, 'topics': [event_signature], 'fromBlock': int(self.config['tcrank_deploy_block_no']) - 10 });

        logs = []
        try:
            logs = self.web3.eth.getFilterLogs(filt.filter_id)
        finally:
            self.web3.eth.uninstallFilter(filt.filter_id)

        objects_moves = {}
        min_ts = int(time.time())
        max_ts = 0
        for log in logs:
            m = get_event_data(event_abi, log).args
            print(repr(m))

            if (objects_moves.get(m.itemId) is None):
                objects_moves[m.itemId] = []

            # no optimizations now
            index_where_to_insert = 0
            for prev_move in objects_moves[m.itemId]:
                if (m.startTime >= prev_move['start']):
                    index_where_to_insert += 1

            if (m.speed) == 0:
                continue
           
            signed_speed = m.speed
            if m.direction == 0:
                signed_speed = (-1 * signed_speed)

            objects_moves[m.itemId].insert(index_where_to_insert, {
                                                            'start': m.startTime,
                                                            'speed': signed_speed,
                                                            'distance': m.distance,
                                                            'moving_time': m.distance/abs(signed_speed)
                                                            })
            if (m.startTime < min_ts):
                min_ts = m.startTime
            min_ts -= 3600

            plan_end = m.startTime + round(m.distance/m.speed)
            if (plan_end > max_ts):
                max_ts = plan_end + 3600

        data = []
        # MUST be sorted by start time
        for item_id in objects_moves:
            mvs = objects_moves[item_id]
            (x_series, y_series) = self.gen_xy_for_object(objects_moves[item_id], INIT_RANK, min_ts, max_ts)
            dapp = self.dapps.get(str(item_id))
            if (dapp is None):
                print("No object with id:{} in local dapps".format(item_id))
                continue
            name = self.dapps.get(str(item_id), {}).get('name')
            data.append(go.Scatter(x=x_series, 
                                   y=y_series,
                                   name="[{}] {}".format(item_id, name),
                                   line=dict(shape='linear'),
                                  ))
            i = 0
        
        layout = { 'title': 'Dapps ranks',
                 }
        fig = dict(data=data, layout=layout)
        plotly.offline.plot(fig, output_type='file', filename=output_file)
        print("Saved output plot to '{}'".format(output_file))
        return

    
    def gen_xy_for_object(self, moves, init_rank, min_ts, max_ts):

        x_series = [] # np.arange(zero_ts, max_ts, 60)
        y_series = []
        last_y = init_rank

        first = True
        if (len(moves) == 0):
            return ([min_ts, max_ts], [init_rank, init_rank])

        cur_x = min_ts
        cur_y = init_rank
        cur_speed = 0
        cur_mov_ind = 0
        x_series.append(datetime.datetime.utcfromtimestamp(cur_x))
        y_series.append(cur_y/1000000000000000000)
    
    
        for m in moves:
            cur_x = m['start']
            x_series.append(datetime.datetime.utcfromtimestamp(cur_x))
            y_series.append(cur_y/1000000000000000000)
            
            cur_speed += m['speed']

            if (cur_speed == 0):
                continue
            cur_x = m['start'] + m['moving_time']
            cur_y = self.mov_func_y_from_t(cur_y, cur_x - m['start'], cur_speed, m['distance'])
            x_series.append(datetime.datetime.utcfromtimestamp(cur_x))
            y_series.append(cur_y/1000000000000000000)

        
        cur_x = max_ts
        x_series.append(datetime.datetime.utcfromtimestamp(cur_x))
        y_series.append(cur_y/1000000000000000000)
        
        # i=0
        # for x in x_series:
        #   print("{}, {}".format(x_series[i], y_series[i]))
        #   i += 1

        return(x_series, y_series)

