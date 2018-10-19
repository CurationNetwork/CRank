#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import time
import argparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import re
import json
import hashlib
import os.path
import random
# import numpy as np


def dd(data):
    print(json.dumps(data, indent=4, sort_keys=True))

def get_config(args):
    return {
        "curator_types": {
            'whale': 0.1,
            'user': 0.9,
        },
        "vote_power": 10
    }


class Curator(object):
    def __init__(self, id):
        self.id = id
        self.type = 'user'
        self.balance = 1000
        self.stats = {"profit": 0.0}

    def __repr__(self):
        return "(Curator[{}], {}, balance: {}, profit: {})".format(self.id, self.type, self.balance, self.stats['profit'])

    def vote_on_dapp(self, dapp, impulse):
        if (dapp.voting_state == 'none'):
            dapp.commits[self.id] = impulse
            dapp.voting_state = 'commit'
            return None

        if (dapp.voting_state == 'commit'):
            dapp.commits[self.id] = impulse
            if (random.uniform(0,1) <  0.2):
                dapp.voting_state = 'reveal'
            return None

            
        if (dapp.voting_state == 'reveal'):
            if dapp.commits.get(self.id) is None:
                return None
            dapp.reveals[self.id] = dapp.commits[self.id]
            if (random.uniform(0,1) <  0.2):
                dapp.voting_state = 'finish'
            return None
 
        if (dapp.voting_state == 'finish'):
            final_impulse = 0
            for vid in dapp.reveals:
                final_impulse += dapp.reveals[vid]

            dapp.rank += final_impulse
            dapp.commits = {}
            dapp.reveals = {}
            dapp.voting_state = 'none'
            return None


class Dapp(object):
     def __init__(self, id):
        self.id = id
        self.name = 'dapp' + str(round(random.random()))
        self.rank = round(random.random())
        self.voting_state = 'none'
        self.commits = {}
        self.reveals = {}
        self.rewards = {}

        self.beauty = random.uniform(0,1)

     def __repr__(self):
        return "(DApp[{}], {}, rank: {}, beauty: {}, voting: {})".format(self.id, self.name, self.rank, self.beauty, self.voting_state)


def main(arguments):

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # parser.add_argument('-fff', '--file', help="File", type=argparse.FileType('r'))
    args = parser.parse_args(arguments)
    config = get_config(args)

    users = []
    for i in range(1,5):
        users.append(Curator(i))

    dapps = []
    for i in range(1,5):
        dapps.append(Dapp(i))


    for i in range(1,400):
        random.choice(users).vote_on_dapp(random.choice(dapps), config['vote_power'])


    print(repr(dapps))
if __name__ == '__main__':
    start = time.time()
    sys.exit(main(sys.argv[1:]))
