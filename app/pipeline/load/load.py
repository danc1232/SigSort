import json
import time
import os

from utilities import queue_client as qclient
from utilities import config_util as util

import requests

def post_entry(data):
    '''post entry to database'''
    _headers = {'Content-Type': 'application/json'}
    _url = f"http://{API_HOST}:{API_PORT}/entries"
    try:
        _r = requests.post(url=_url, data=json.dumps(data), headers=_headers, timeout=10)
    except requests.exceptions.RequestException as e:
        log.error(f"error making request: {e}")
        time.sleep(5)
        post_entry(data)
    time.sleep(app_conf['post-delay'])

def callback(ch, method, _properties, body):
    '''callback on message received'''
    msg = json.loads(body)
    ### IF UPDATE MSG RECEIVED
    if msg.get('refresh'):
        config.reload_config()
    else:
        post_entry(msg)
    ch.basic_ack(delivery_tag=method.delivery_tag)

# ENV VARS / CONSTANTS
API_HOST = os.environ['API_HOST']
API_PORT = os.environ['API_PORT']
QUEUE_HOST = os.environ['QUEUE_HOST']
CONF_FILE = 'config.yaml'
IN_KEY = "load"

# CONFIG SETUP
config = util.Config(CONF_FILE)
log = config.get_logger()
global_conf = config.get_subconfig(('global',))
app_conf = config.get_subconfig(('pipeline','load'))

# Wait for RabbitMQ to wake up
time.sleep(int(global_conf['message-queue-delay']))

# Initiate RabbitMQ connection
client = qclient.RabbitMQClient(host=QUEUE_HOST)

# start consuming inbound queue and begin passing messages
client.consume(IN_KEY, callback)
