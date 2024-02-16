import json
import time
import os
import re

import spacy

from utilities import queue_client as qclient
from utilities import config_util as util

def clean_text(text):
    '''remove extra spaces and punctuation'''
    text = text.replace("\n", " ").replace("\r", " ")
    punc_list = '!"#$%&()*+,-./:;<=>?@[\\]^_{|}~'
    t = str.maketrans(dict.fromkeys(punc_list, " "))
    text = text.translate(t)
    t = str.maketrans(dict.fromkeys("'`", " "))
    text = text.translate(t)
    return text

def manual_extract(data, capture_groups):
    '''Parse manually-listed entities'''
    text = clean_text(data['title'] + ' ' + data['summary'])
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
            if gname not in data['entities']:
                data['entities'].append(gname)
    return data

def spacy_ner(data):
    '''Parse entities using spaCy NER'''
    text = clean_text(data['title'] + ' ' + data['summary'])
    doc = nlp(text)
    entities = []
    labels = app_conf['auto']['steps']['spaCy']['labels']
    # parse out entities from tokenized doc
    for ent in doc.ents:
        if ent.label_ in labels:
            entities.append(ent.text)
    # add entities that aren't already present
    for ent in entities:
        if ent not in data['entities']:
            data['entities'].append(ent)
    return data

def callback(ch, method, _properties, body):
    '''callback on message received'''
    msg = json.loads(body)
    ### IF UPDATE MSG RECEIVED
    if msg.get('refresh'):
        ### REFRESH HERE AND PUSH UPDATE TO NEXT STEP
        config.reload_config()
        client.publish(app_conf['routing']['out'], msg)
    else:
        # PROCESS ENTRY
        if app_conf['manual']['enabled']:
            cap_groups = app_conf['manual']['capture-groups']
            msg = manual_extract(msg, cap_groups)
        if app_conf['auto']['enabled']:
            # spaCy
            if app_conf['auto']['steps']['spaCy']['enabled']:
                msg = spacy_ner(msg)
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
app_conf = config.get_subconfig(('pipeline','entity'))

# load spaCy model (even if disabled - just in case!)
nlp = spacy.load(app_conf['auto']['steps']['spaCy']['model'])

# Wait for RabbitMQ to wake up
time.sleep(global_conf['message-queue-delay'])

client = qclient.RabbitMQClient(host=QUEUE_HOST)

# start consuming inbound channel and begin passing messages
client.consume(app_conf['routing']['in'], callback)
