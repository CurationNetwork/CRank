#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import time
import argparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import sha3
from ecdsa import SigningKey, SECP256k1
import re
import json
import hashlib
import os.path
import random


def dd(data):
    print(json.dumps(data, indent=4, sort_keys=True))


class Curator(object):
    def __init__(self, id, creds):
        self.id = id
        self.type = 'user'
        self.address = creds['address']
        self.public_key = creds['public_key']
        self.private_key = creds['private_key']
        self.balance = 0
        self.stats = {"profit": 0.0}

    def __repr__(self):
        return "(Curator[{}], {}, balance: {}, profit: {})".format(self.id, self.type, self.balance, self.stats['profit'])



class Dapp(object):
     def __init__(self, id):
        self.id = id
        self.name = 'dapp' + str(round(random.random()))
        self.rank = round(random.random())
        self.voting = None

        self.beauty = random.uniform(0,1)

     def __repr__(self):
        return "(DApp[{}], {}, rank: {}, beauty: {}, voting: {})".format(self.id, self.name, self.rank, self.beauty, self.voting_state)


class RegistryModel(object):

    def __init__(self, config):
        self.config = config

        self.users = {}
        i = 0
        for creds in self.config['accounts']:
            self.users[i] = Curator(i, creds)
            i += 1  

        N_dapps = 5
        self.dapps = {}
        for i in range(N_dapps):
            self.dapps[i] = Dapp(i)
    
    def __enter__(self):
        print("enter");
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        print("exit");
        pass

    def get_random_user_id(self):
        return random.choice(range(5))

    def get_random_dapp_id(self):
        return random.choice(range(5))


    def vote_on_dapp(self, user_id, dapp_id, impulse):
        # skip all "commit-reveal" - only votes added
        if self.dapps[dapp_id].voting is None:
            self.dapps[dapp_id].voting = {}

        self.dapps[dapp_id].voting[user_id] = impulse


    def finish_vote_on_dapp(self, dapp_id):
        if (self.dapps[dapp_id].voting is None):
            # print("DApp[{}], error: finish on closed voting".format(dapp_id))
            return None
        final_impulse = 0
        for voter in self.dapps[dapp_id].voting:
            final_impulse += self.dapps[dapp_id].voting[voter]

        print("DApp[{}], finish voting, final impulse: {}, votes: ({})"
              .format(dapp_id, final_impulse, self.dapps[dapp_id].voting))

        self.dapps[dapp_id].voting = None


    def user_decide_and_vote(self, user_id):

        # choose dapp to work
        dapp_id = self.get_random_dapp_id()

        # choose impulse
        impulse = int(random.uniform(0,1) * 100) - 50

        self.vote_on_dapp(user_id, dapp_id, impulse)

    def finish_all_votings(self):
        for dapp_id in self.dapps:
            self.finish_vote_on_dapp(dapp_id)


