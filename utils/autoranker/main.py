#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import time
import argparse
from queue import Queue
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import re
import json
import hashlib
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

from autoranker import Autoranker, INIT_RANK


def get_config(args):
    config = {
        "eth_http_node": "https://rinkeby.infura.io/v3/1474ceef2da44edbac41a2efd66ee882",
        # "eth_http_node": "http://10.100.11.24:8545",


        # "tcrank_address": "0x6a91ff9271406d421c75e6b6dd04fb1f7857cb30",
        # "tcrank_deploy_block_no": "3148631",
        # "faucet_address": "0xf41c3d0e08b10930ae85144a7b98231bc1f22e21",

        # "tcrank_address": "0xdd5c07c484778ae52b5e60999bf625a998c265b4",

        "helper_address": "0x8266a0b43c171e645bb56f8a76c4e6ef4b5fad5d",
        
        # LAST
        "tcrank_address": "0xb6c77b0365a3f5830579dea88126d3a77f4e8587",
        "tcrank_deploy_block_no": "3164581",
        "faucet_address": "0x3171fa7390f083fa40a7184b0a51e344c4f83d23",

        "dapps_import_url": "https://stage.curation.network/api/store/projects/export",
    }

    with open("../../solidity/smartz/ranking.abi") as json_data:
        config['tcrank_abi'] = json.load(json_data)

    with open("../../solidity/smartz/faucet.abi") as json_data:
        config['faucet_abi'] = json.load(json_data)

    with open("../../solidity/smartz/helper.abi") as json_data:
        config['helper_abi'] = json.load(json_data)

    if (args.keys_file):
        config['keys_file'] = args.keys_file.name
        config['accounts'] = json.load(args.keys_file)

    return config

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

def main(arguments):

    logger = logging.getLogger('autoranker')
    fh = logging.FileHandler('/tmp/autoranker.log')
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
    fh.setFormatter(formatter)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-k', '--keys-file', help="File with keys and addresses", type=argparse.FileType('r'))
    parser.add_argument('--dapp-id', action="store", type=int, help="performs operation for selected dapp id (randomplay or syncdapps)")
    parser.add_argument('--random-play', action="store_true", help="begins to push dapps randomly")
    parser.add_argument('--generate-keys-pack', action="store_true", help="outputs pack of keypairs + eth addresses")
    parser.add_argument('--sync-dapps', action="store_true", help="begins to renew dapps in contract(if owner)")
    parser.add_argument('--show-ranking', action="store_true", help="outputs ranking from contract")
    parser.add_argument('--ranking-history', action="store_true", help="outputs ranking history")
    parser.add_argument('--ranking-history-output-png', type=str, action="store", help="outputs ranking history into PNG file ")

    args = parser.parse_args(arguments)
    
    config = get_config(args)

    # GENERATES ARRAY OF DICTS with private,public keys and addresses
    if (args.generate_keys_pack == True):
        keys = []
        n = 0
        while (n < 7):
            keys.append(generate_keypair_and_address())
            n += 1
        print(json.dumps(keys, indent=4, sort_keys=True))
        return


    their_dapps = get_json_from_url(config['dapps_import_url'], 0)
    if (not their_dapps):
        print("No dapps loaded from '{}', stop".format(config['dapps_import_url']))
        return

    dapps = {}
    for d in their_dapps:
        id = str(d.get('id'))
        dapps[id] = { 'id': id,
                      'name': d.get('name'),
                      'their_rank': d.get('rank')
                    }

    # now create autoranker object and pass contract and account to it. Any further logic must be implemented in Autoranker class
    autoranker = Autoranker(config, dapps)
  
    max_rank = 0

    for dapp_id in autoranker.dapps:
        d = autoranker.dapps[dapp_id]
        if d['their_rank'] > max_rank:
            max_rank = d['their_rank']

    avg_stake = INIT_RANK
    rank_step = avg_stake * 2 / max_rank # take max rank and make all dapps_rank proportional
    for dapp_id in autoranker.dapps:
        d = autoranker.dapps[dapp_id]
        autoranker.dapps[dapp_id]['rank'] = round(autoranker.dapps[dapp_id]['their_rank'] * rank_step)
        # print("rank of item [{}]: {} ({}), calculated from max rank: {} ({}) and their_rank: {}"
        #       .format(dapp_id,
        #               autoranker.dapps[dapp_id]['rank'],
        #               round(autoranker.dapps[dapp_id]['rank'] / 1e18),
        #               avg_stake * 2, round(avg_stake * 2 / 1e18),
        #               autoranker.dapps[dapp_id]['their_rank']))


    if (args.show_ranking == True):
        autoranker.show_ranking()
        return

    single_dapp_id = args.dapp_id
    if (args.ranking_history == True):
        output_file = args.ranking_history_output_png
        autoranker.ranking_history(single_dapp_id, output_file)
        return

    if (args.sync_dapps == True):
        autoranker.load_dapps_to_contract(single_dapp_id)
        return

    if (args.random_play == True):
        autoranker.start_moving_dapps(single_dapp_id)
        return

    print("Do nothing...")



def to_32byte_hex(val):
    return Web3.toHex(Web3.toBytes(val).rjust(32, b'\0'))



def get_json_from_url(url,
                      cache_ttl=86400, # TTL of downloaded cached file with JSON. Before this time URL will not be downloaded, contents will be taken from cached file
                      ):
    # logger.debug(" getting JSON from url: '{}'".format(url))
    if (url is None or not isinstance(url, str)):
        logger.error("Wrong url param empty or not a string")
        return None
    
    md5hasher = hashlib.md5()
    md5hasher.update(url.encode('utf-8'))
    urlhash = md5hasher.hexdigest() # use global hasher if highloads

    filename = '/tmp/' + 'autoranker_cache_json_' + urlhash

    if (os.path.isfile(filename)):
        st = os.stat(filename)
        age = round(time.time() - st.st_mtime)
        if (age < cache_ttl):
            # logger.debug("file '{}' already exists, age: {} < {}, using cached".format(filename, age, cache_ttl))
            file = open(filename, "r")
            json_text = file.read()
            file.close()
            result = None
            try:
                result = json.loads(json_text)
                return result
            except:
                logger.error("cannot decode cached JSON from file: '{}'".format(filename))

    json_body = None
    try_count = 0
    max_tries=2
    while (try_count <= max_tries):
        try_count = try_count + 1
        try:
            req = Request(   url,
                      data=None,
                      headers={
                         'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
                      }
            )
            res = urlopen(req)
            json_body = res.read()
        except HTTPError as e:
            if (e.code == 429): # too many requests
                logger.debug("Too many requests for url: '{}', sleeping for {}s, try {}".format(url, sleep_when_429, try_count))
                time.sleep(sleep_when_429)
        except Exception as e:
            logger.error("cannot get JSON from url '{}', try {}: {}".format(url, try_count, repr(e)))
    
    if (json_body is None):
        logger.error("no JSON from url '{}', tries: {}".format(url, try_count))

    # save cached copy
    try:
        result = json.loads(json_body)
        with open(filename, 'w') as outfile:
            json.dump(result, outfile)
            # logger.debug("JSON contents saved to file: '{}'".format(filename))
            return result
    except Exception as e:
        logger.error("cannot parse JSON from downloaded url '{}': {}".format(url, repr(e)))
    
    return None



if __name__ == '__main__':
    start = time.time()
    sys.exit(main(sys.argv[1:]))

