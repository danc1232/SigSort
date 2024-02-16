import json
from datetime import date
import time
import re
import os

from rapidfuzz import fuzz

from utilities import queue_client as qclient
from utilities import config_util as util

def remove_cves(data):
    '''Remove any CVEs from non-vuln fields'''
    log.debug("staring CVE removal")
    log.debug("pre-pass keys:")
    log.debug(data['keywords'])
    kept_keys = set()
    for i in data['keywords']:
        if re.search(CVE_PATTERN, i):
            continue
        kept_keys.add(i)
    data['keywords'] = kept_keys
    log.debug("post-pass keys:")
    log.debug(kept_keys)

    log.debug("pre-pass entities:")
    log.debug(data['entities'])
    kept_ents = set()
    for e in data['entities']:
        if re.search(CVE_PATTERN, e):
            continue    
        kept_ents.add(e)
    data['entities'] = kept_ents
    log.debug("post-pass entities")
    log.debug(kept_ents)
    return data

def rapidfuzz_dedupe(item_list, threshold):
    '''implementation of RapidFuzz to deduplicate fields'''
    unique_items = []
    log.debug('pre-list:')
    log.debug(item_list)
    for item in item_list:
        if all(fuzz.ratio(item, unique_item) < threshold for unique_item in unique_items):
            unique_items.append(item)
    log.debug('post-list:')
    log.debug(unique_items)
    return unique_items

def callback(ch, method, _properties, body):
    '''callback on message received'''
    msg = json.loads(body)
    if msg.get('refresh'):
        config.reload_config()
        client.publish(app_conf['routing']['out'], msg)
    else:
        # remove CVEs from keywords/entities
        msg = remove_cves(msg)
        # perform deduplication if enabled
        if app_conf['deduplicate']['enabled']:
            dd_conf = app_conf['deduplicate']
            if dd_conf['steps']['rapidfuzz']['enabled']:
                th = dd_conf['steps']['rapidfuzz']['threshold']
                log.debug('starting rapidfuzz_dedupe on keywords')
                msg['keywords'] = rapidfuzz_dedupe(msg['keywords'], th)
                log.debug('starting rapidfuzz_dedupe on entities')
                msg['entities'] = rapidfuzz_dedupe(msg['entities'], th)
        client.publish(app_conf['routing']['out'], msg)
    ch.basic_ack(delivery_tag=method.delivery_tag)

# ENV VARS / CONSTANTS
QUEUE_HOST = os.environ['QUEUE_HOST']
CONF_FILE = 'config.yaml'
CVE_PATTERN = re.compile(r"\bCVE\w*")

# CONFIG SETUP
config = util.Config(CONF_FILE)
log = config.get_logger()
global_conf = config.get_subconfig(('global',))
app_conf = config.get_subconfig(('pipeline','post-process'))

# Wait for RabbitMQ to wake up
time.sleep(int(global_conf['message-queue-delay']))

# Initiate RabbitMQ connection
client = qclient.RabbitMQClient(host=QUEUE_HOST)

# start consuming inbound queue and begin passing messages
client.consume(app_conf['routing']['in'], callback)
