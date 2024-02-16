import json
import time
import re
import os
from datetime import datetime
from http.client import IncompleteRead, RemoteDisconnected
import traceback
from bs4 import BeautifulSoup
import requests
import feedparser
import xxhash
import lxml
from dateutil import parser

from utilities import queue_client as qclient
from utilities import config_util as util

def update_feed_success(data):
    '''send feed update (successful)'''
    _headers = {'Content-Type': 'application/json'}
    _url = f"http://{API_HOST}:{API_PORT}/feeds/{data['id']}"

    _data = {
        'updated': datetime.now().isoformat(),
        'fail_reason': None,
        'fail_count': 0,
        'last_fail': None
    }

    match data['method']:
        case 'updated_field':
            _data['updated'] = time.strftime('%Y-%m-%dT%H:%M:%S', data['updated'])
        case 'content_hash':
            _data['content_hash'] = data['content_hash']
        case _:
            log.error('update_feed_success(): passed invalid "method" value')

    try:
        requests.put(url=_url, data=json.dumps(_data), headers=_headers, timeout=20)
    except requests.exceptions.RequestException as e:
        log.error(f"error making request: {e}")
        time.sleep(10)
        update_feed_success(data)

def update_feed_fail(feed_id, fail_count, fail_reason):
    '''send feed update (failure)'''
    _url = f"http://{API_HOST}:{API_PORT}/feeds/{feed_id}"
    _headers = {'Content-Type': 'application/json'}
    fails = int(fail_count) + 1
    _data = {
        'fail_count': fails,
        'fail_reason': fail_reason,
        'last_fail': datetime.now().isoformat()
    }
    if fails >= 3:
        _data['status'] = False
    try:
        requests.put(url=_url, data=json.dumps(_data), headers=_headers, timeout=20)
    except requests.exceptions.RequestException as e:
        log.error(f"error making request: {e}")
        time.sleep(10)
        update_feed_fail(feed_id, fail_count, fail_reason)

def check_entry_hash(entry_id):
    '''Query database to see if entry already exists'''
    _url = f"http://{API_HOST}:{API_PORT}/entries/hash/{entry_id}"
    r = requests.get(url=_url, timeout=3)
    log.debug(f'check_entry_hash: r.status: {r.status_code}')
    if r.status_code == 200:
        return True
    return False

def clean_text(text):
    '''Remove HTML tags, entities, and extra newlines / whitespace from text'''
    # remove html
    text = remove_html(text)
    # remove entities
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    # remove newlines, extra spaces
    text = re.sub(r'\s+', ' ', text)
    # remove trailing whitespace
    return text.strip()

def remove_html(text):
    '''Remove HTML tags and other content from text'''
    try:
        soup = BeautifulSoup(text, "lxml")
        return soup.text
    except Exception as e:
        log.error(f"error removing html: {e}")
        return text

def standardize_datetime(date_string):
    '''Parse datetime object into standard format'''
    try:
        dt_string = parser.parse(date_string)
        return dt_string.astimezone().strftime('%b %d, %Y %I:%M %p %z')
    except ValueError:
        return date_string

def parse_feed_data(data, feed_id):
    '''Parse entries from feed'''
    parsed_entries = []
    for e in data.entries:
        # confirm necessary fields exist in this entry
        if None in [e.get('title'),e.get('summary'),e.get('link'),e.get('published')]:
            continue
        # create new entry object to pass along to proc pipeline
        entry = {}
        content_sig = e['title'] + ' ' + e['link']
        # create content hash to use as entry ID
        entry['id'] = int(str(xxhash.xxh3_64(str(content_sig)).intdigest())[:16])

        # does entry already exist?
        exists = check_entry_hash(entry['id'])
        if not exists:
            entry['title'] = clean_text(e['title'])
            entry['link'] = e['link']
            entry['summary'] = clean_text(e['summary'])
            log.debug(f"POST clean_text summary: {entry['summary']}")
            entry['pub_date'] = standardize_datetime(e['published'])
            entry['keywords'] = []
            entry['entities'] = []
            entry['full_text'] = ""
            entry['feed'] = feed_id
            parsed_entries.append(entry)
    return parsed_entries

def fetch(feed):
    """
    Fetch data from specified RSS feed
    """
    try:
        f = feedparser.parse(feed['url'])
        # if parse request didn't return 200, fail out
        if hasattr(f, 'status'):
            log.debug(f"f.status: {f.status}")
            if f.status != 200:
                return {
                    'id': feed['id'],
                    'status': 'fail',
                    'fail_reason': f"non-200 status code: {f.status}",
                    'fail_count': feed['fail_count']
                }
        else:
            log.debug(f"feed {feed['name']} does not have status")
            return {
                    'id': feed['id'],
                    'status': 'fail',
                    'fail_reason': "failed to fetch, f.status not defined",
                    'fail_count': feed['fail_count']
                }

        ### IF FEED.UPDATED FIELD IS POPULATED, USE IT ###
        if hasattr(f, 'updated_parsed'):
            log.debug('feed has updated_parsed attribute available')
            time_string = feed['updated'].replace('"','').rsplit("+",1)[0]
            old_time = datetime.strptime(time_string, '%Y-%m-%dT%H:%M:%S').timetuple()
            new_time = f.updated_parsed
            log.debug(f'last update according to DB (old_time): {old_time}')
            log.debug(f'last update according to feed (new_time): {new_time}')
            if new_time > old_time:
                # FEED IS NEW / UPDATED
                log.debug('feed is new / updated, parsing entries...')
                entries = parse_feed_data(f, feed['id'])
                return {
                    'id': feed['id'],
                    'status': 'updated',
                    'method': 'updated_field',
                    'entries': entries,
                    'updated': f.updated_parsed
                }
            log.debug('feed has not been updated, status unchanged')
            return {'status': 'unchanged'}

        log.debug('feed does not have updated attribute, falling back to content hash')
        ### IF FEED.UPDATED IS NOT AVAILABLE, FALL BACK TO FEED CONTENT HASHES
        content_hash = int(str(xxhash.xxh3_64(str(f)).intdigest())[:16])
        # if content_hash is defined, check against existing value
        if feed.get('content_hash'):
            log.debug('feed in DB has defined content_hash, checking for update')
            if content_hash == feed['content_hash']:
                log.debug('feed hash is equal to stored hash, status unchanged')
                return {'status': 'unchanged'}
        # if content hash doesn't exist yet for this feed, it's new
        # (or the feed has stopped publishing the "updated" field) - either way, update
        log.debug('hash is new or undefined, parsing entries...')
        entries = parse_feed_data(f, feed['id'])
        return {
            'id': feed['id'],
            'status': 'updated',
            'method': 'content_hash',
            'entries': entries,
            'content_hash': content_hash
        }

    except IncompleteRead:
        # SEND DIRECTLY TO LOAD QUEUE WITH INCREMENTED FAIL COUNT AND fail_reason
        return {
            'id': feed['id'],
            'status': 'fail',
            'fail_reason': 'incomplete read',
            'fail_count': feed['fail_count']
        }

    except RemoteDisconnected:
        # SEND DIRECTLY TO LOAD QUEUE WITH INCREMENTED FAIL COUNT AND fail_reason
        return {
                'id': feed['id'],
                'status': 'fail',
                'fail_reason': 'remote disconnected',
                'fail_count': feed['fail_count']
            }
    
    except Exception:
        # ANY OTHER EXCEPTION
        log.error("unrecognized exception in fetch()")
        log.error(traceback.format_exc())
        return {
            'id': feed['id'],
            'status': 'fail',
            'fail_reason': f"other: {traceback.format_exc()}",
            'fail_count': feed['fail_count']
        }

def callback(ch, method, _properties, body):
    '''callback on message received'''
    msg = json.loads(body)
    ### IF UPDATE MSG RECEIVED
    if msg.get('refresh'):
        ### REFRESH HERE AND PUSH UPDATE TO NEXT STEP
        config.reload_config()
        client.publish(app_conf['routing']['out'], msg)
    else:
        log.debug(f"feed: {msg}")
        parsed = fetch(msg)
        if parsed['status'] == 'unchanged':
            log.debug(f"feed {msg['id']} unchanged.")
        elif parsed['status'] == 'updated':
            log.debug(f"feed {parsed['id']} updated")
            # publish entries to pipeline
            for entry in parsed['entries']:
                client.publish(app_conf['routing']['out'], entry)
            # also send feed update
            update_feed_success(parsed)
        else:
            update_feed_fail(parsed['id'], parsed['fail_count'], parsed['fail_reason'])
    ch.basic_ack(delivery_tag=method.delivery_tag)

# ENV VARS / CONSTANTS
API_HOST = os.environ['API_HOST']
API_PORT = os.environ['API_PORT']
QUEUE_HOST = os.environ['QUEUE_HOST']
CONF_FILE = 'config.yaml'
IN_KEY = "ingest"

# CONFIG SETUP
config = util.Config(CONF_FILE)
log = config.get_logger()
global_conf = config.get_subconfig(('global',))
app_conf = config.get_subconfig(('pipeline','ingest'))

# Wait for RabbitMQ to wake up
time.sleep(int(global_conf['message-queue-delay']))
client = qclient.RabbitMQClient(host=QUEUE_HOST)

# start consuming ingest queue and begin passing messages
client.consume(IN_KEY, callback)
