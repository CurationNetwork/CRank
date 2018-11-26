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

from RegistryModel import RegistryModel, Curator, Dapp


def dd(data):
    print(json.dumps(data, indent=4, sort_keys=True))


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


def get_config(args):
    config = {
        "curator_types": {
            'whale': 0.1,
            'user': 0.9,
        },
        "vote_power": 10
    }

    # [FIXME] temp shit
    if (args.migrate_cmd):
        config['migrate_cmd'] = args.migrate_cmd
        config['migrate_cwd'] = args.migrate_cwd
        
    if (args.keys_file):
        config['accounts'] = json.load(args.keys_file)

    return config


def main(arguments):

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--migrate-cmd', required=True, help="Ranking contract migration command", type=str)
    parser.add_argument('--migrate-cwd', required=True, help="Ranking contract migration command working directory", type=str)
    parser.add_argument('-k', '--keys-file', required=True, help="File with keys and addresses", type=argparse.FileType('r'))
    # parser.add_argument('--gen-deploy-command', help="generate ganache cli command", type=bool)

    args = parser.parse_args(arguments)
    config = get_config(args)
    
    # can be a long array (because we add all accounts from file with keys
    config['ganache_cmd'] = ["ganache-cli"]

    accs = []
    for creds in config['accounts']:
        config['ganache_cmd'].append("--account=\"0x{},0xFFFFFFFFFFFFFFFF\"".format(creds['private_key']))
    
    config['ganache_cmd'].append("-l 7000000000000000000")

    # print(" ".join(config['ganache_cmd']))

    # Registry model creates subprocess (ganache-cli with pre-defined users ant ether balances)
    # after using RegistryModel stops ganache-cli process
    with RegistryModel(config) as model:
        model = RegistryModel(config);

        #for i in range(1,40):
        #    user_id = model.get_random_user_id()
        #    model.user_decide_and_vote(user_id)

        #model.finish_all_votings()

    
    sys.exit(0)



if __name__ == '__main__':
    start = time.time()
    sys.exit(main(sys.argv[1:]))
