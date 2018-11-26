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
import subprocess
from subprocess import TimeoutExpired
import os
import signal
import shlex


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


def log_subprocess_output(process_name, pipe):
    for line in iter(pipe.readline, b''): # b'\n'-separated lines
        print('[{}]: {}'.format(process_name, line))

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

        self.ganache_proc = None
        self.ganache_pid = None
        self.ganache_stdout = None
        self.ganache_stderr = None
    
    def __enter__(self):
        print("[DEBUG] Running ganache process: {} (+accounts part)"
              .format(" ".join(self.config['ganache_cmd'])))
        self.ganache_proc = subprocess.Popen(self.config['ganache_cmd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        with self.ganache_proc.stdout:
            for line in iter(self.ganache_proc.stdout.readline, b''): # b'\n'-separated lines
                print('[ganache]: {}'.format(str(line)))
                if str(line).find('Listening on') != -1:
                    print("Ganache started, trying to deploy contracts")
                    break;
            
            self.migrate_proc = subprocess.Popen(self.config['migrate_cmd'], cwd=self.config['migrate_cwd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            with self.migrate_proc.stdout:
                for line in iter(self.migrate_proc.stdout.readline, b''): # b'\n'-separated lines
                    print('[migration]: {}'.format(str(line)))

            self.migrate_proc.wait()


    # exitcode = self.ganache_proc.wait()
  
#        try:
#            self.ganache_stdout, self.ganache_stderr = self.ganache_proc.communicate(timeout=15)
#            self.ganache_pid = self.ganache_proc.pid 
#        except TimeoutExpired as e:
#            print("[DEBUG] Timeout exception when running ganache process: {} (+accounts part): {}"
#                  .format(self.config['ganache_cmd'][0], repr(e)))
#            self.ganache_proc.kill()
#            self.ganache_stdout, self.ganache_stderr = self.ganache_proc.communicate(timeout=15)
#        except KeyboardInterrupt:
#            print("[DEBUG] Keyboard interrupt ganache process: {} (+accounts part)"
#                  .format(self.config['ganache_cmd'][0]))
#            try:
#                self.ganache_proc.terminate()
#            except OSError:
#                pass
#            self.ganache_proc.wait()
#        except Exception as e:
#            print("[Error] Exception running ganache process: {} (+accounts part): {}"
#                  .format(self.config['ganache_cmd'][0], repr(e)))
#            self.ganache_proc.kill()
#            self.ganache_stdout, self.ganache_stderr = self.ganache_proc.communicate(timeout=15)
#          
#        print(self.ganache_stderr)
#
        # self.deploy_contracts()
        
        return True

    def __exit__(self, exc_type, exc_value, traceback):
        print("[DEBUG] Exit context of ganache process with PID: {}".format(self.ganache_pid))
        self.ganache_proc.kill()
        return True
        # os.killpg(os.getpgid(self.ganache_pid), signal.SIGTERM)


    def run_command_sync_display_output(self, command, workdir):
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, cwd=workdir)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(str(output.strip()))
        rc = process.poll()
        return rc

    def deploy_contracts(self):
        self.run_command_sync_display_output("truffle migrate --network development", "../../solidity/")
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


