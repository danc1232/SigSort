import time
import os
import requests

from utilities import config_util as util

def fetch_feed_updates(host, port):
    '''Send fetch request to API'''
    _url = f"http://{host}:{port}/fetch"
    try:
        requests.get(url=_url, timeout=10)
    except Exception:
        log.info("api not listening yet, sleeping")
        time.sleep(30)
        fetch_feed_updates(host, port)

# ENV VARS / CONSTANTS
CONF_FILE = 'config.yaml'

# CONFIG SETUP
config = util.Config(CONF_FILE)
log = config.get_logger()
global_conf = config.get_subconfig(('global',))
app_conf = config.get_subconfig(('other','scheduler'))

def main():
    interval_seconds = int(app_conf['refresh']['interval'])
    initial_delay = int(app_conf['refresh']['initial-delay'])
    host = os.environ['API_HOST']
    port = os.environ['API_PORT']

    # wait for everything to get spun up
    time.sleep(initial_delay)

    if app_conf['refresh']['enabled']:
        while True:
            # config.reload_config()
            interval_seconds = app_conf['refresh']['interval']
            # update every interval, indefinitely
            fetch_feed_updates(host, port)
            time.sleep(interval_seconds)

if __name__ == "__main__":
    main()
