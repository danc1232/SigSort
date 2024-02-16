import re
import json
import time
import os

from utilities import queue_client as qclient
from utilities import config_util as util

def parse_cves(data):
    text = (data['title'] + ' ' + data['summary']).upper()
    CVEs = CVE_PATTERN.findall(text)
    CVEs = list(set(CVEs))
    data['vulns'] = CVEs
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
        if app_conf['enabled']:
            msg = parse_cves(msg)
        client.publish(app_conf['routing']['out'], msg)
    ch.basic_ack(delivery_tag=method.delivery_tag)

# ENV VARS / CONSTANTS
QUEUE_HOST = os.environ['QUEUE_HOST']
CONF_FILE = 'config.yaml'
CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,}")

# CONFIG SETUP
config = util.Config(CONF_FILE)
log = config.get_logger()
global_conf = config.get_subconfig(('global',))
app_conf = config.get_subconfig(('pipeline', 'cve'))

# Wait for RabbitMQ to wake up
time.sleep(int(global_conf['message-queue-delay']))

# Initiate RabbitMQ connection
client = qclient.RabbitMQClient(host=QUEUE_HOST)

# start consuming inbound queue and begin passing messages
client.consume(app_conf['routing']['in'], callback)
