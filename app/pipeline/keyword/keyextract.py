import time
import os
import json
import re

from utilities import queue_client as qclient
from utilities import config_util as util

import yake

def clean_text(text):
    '''Remove whitespace / punctuation'''
    text = text.replace("\n", " ").replace("\r", " ")
    punc_list = '!"#$%&()*+,-./:;<=>?@[\\]^_{|}~'
    t = str.maketrans(dict.fromkeys(punc_list, " "))
    text = text.translate(t)
    t = str.maketrans(dict.fromkeys("'`", " "))
    text = text.translate(t)
    return text

def manual_extract(entry, capture_groups):
    '''manual extraction of keywords'''
    text = clean_text(entry['title'] + ' ' + entry['summary'])
    words = WORD.findall(text)
    for group in capture_groups:
        patterns = []
        # if top-level item is a str, check for it as a pattern
        if isinstance(group, str):
            gname = group
            patterns.append(group)
            patterns.append(group.lower())
        # if top-level item is a dict, add its key and look for nested patterns
        elif isinstance(group, dict):
            for key, val in group.items():
                gname = key
                patterns.append(key)
                patterns.append(key.lower())
                if 'patterns' in val:
                    patterns.extend(val['patterns'])
        found = False
        for p in patterns:
            if p in words:
                found = True
                break
        if found:
            if gname not in entry['keywords']:
                entry['keywords'].append(gname)
    return entry

def yake_extract(entry, yake_conf):
    '''implementation of YAKE extraction'''
    log.debug('entering yake_extract()')
    max_n = yake_conf['max-ngram-size']
    dupe_t = yake_conf['deduplication-th']
    key_num = yake_conf['keys-per-ngram']
    max_keys = yake_conf['max-total-keys']
    max_wgt = yake_conf['weight-cutoffs']
    
    text = clean_text(entry['title']) + ' ' + clean_text(entry['summary'])
    log.debug('(cleaned) text:')
    log.debug(text)
    # custom_kw_extractor = yake.KeywordExtractor(lan="en", n=max_n, dedupLim=dupe_t, top=key_num, features=None)
    all_keywords = []
    for i in range(max_n):
        log.debug(f"extracting keywords with n size: {i+1}")
        extractor = yake.KeywordExtractor(lan="en", dedupLim=dupe_t, n=i+1, top=key_num, features=None)
        keywords = extractor.extract_keywords(text)
        # create set of keywords of size N
        n_keys = set()
        for keyword, score in keywords:
            log.debug(f'keyword: {keyword}, yake-score: {score}')
            if score <= max_wgt[i]:
                n_keys.add((score,keyword))
        # add sorted key set to full keyword list
        all_keywords.extend(sorted(n_keys))
    all_keywords = [kw for score, kw in all_keywords]

    if max_keys:
        # cut down number of included keys to max_keys (if defined)
        total_keys_included = max_keys
        if total_keys_included > len(all_keywords):
            total_keys_included = len(all_keywords)

        for kw in all_keywords[:total_keys_included]:
            if kw not in entry['keywords']:
                entry['keywords'].append(kw)
    else:
        for kw in all_keywords:
            if kw not in entry['keywords']:
                entry['keywords'].append(kw)
    return entry

def callback(ch, method, _properties, body):
    '''callback on message received'''
    msg = json.loads(body)
    if msg.get('refresh'):
        config.reload_config()
        client.publish(app_conf['routing']['out'], msg)
    else:
        # PROCESS ENTRY
        if app_conf['manual']['enabled']: # if manual parsing broadly enabled
            cap_groups = app_conf['manual']['capture-groups']
            msg = manual_extract(msg, cap_groups)
        if app_conf['auto']['enabled']: # if automatic parsing broadly enabled
            # check for each step / technique
            if app_conf['auto']['steps']['yake']['enabled']: # YAKE
                yake_conf = app_conf['auto']['steps']['yake']
                msg = yake_extract(msg, yake_conf)
        client.publish(app_conf['routing']['out'], msg)
    ch.basic_ack(delivery_tag=method.delivery_tag)

# ENV VARS / CONSTANTS
QUEUE_HOST = os.environ['QUEUE_HOST']
CONF_FILE = 'config.yaml'
WORD = re.compile(r'\w+')

# CONFIG SETUP
config = util.Config(CONF_FILE)
log = config.get_logger()
global_conf = config.get_subconfig(('global',))
app_conf = config.get_subconfig(('pipeline','keyword'))

# Wait for RabbitMQ to wake up
time.sleep(int(global_conf['message-queue-delay']))

client = qclient.RabbitMQClient(host=QUEUE_HOST)

# start consuming ingest queue and begin passing messages
client.consume(app_conf['routing']['in'], callback)
