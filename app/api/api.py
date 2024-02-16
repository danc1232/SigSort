'''api/app.py - interface to communicate between containers and database'''
import json
import time
from datetime import datetime
import os

import yaml

from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from psycopg2 import connect, OperationalError

from utilities import queue_client as qclient
from utilities import config_util as util

class CustomJSONEncoder(json.JSONEncoder):
    '''Custom JSON encoder to automatically handle datetime serialization'''
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

app = Flask(__name__)
app.json_encoder = CustomJSONEncoder
api = Api(app)

### DATABASE UTILITY FUNCTIONS
def get_db_connection():
    '''Establish connection to database'''
    conn = connect(
        host = os.environ['DB_HOST'],
        dbname = os.environ['DB_NAME'],
        user= os.environ['DB_USER'],
        password= os.environ['DB_PASS']
    )
    return conn

def query_db(query, args=(), one=False):
    '''
    Executes specified SELECT query (safely)
    :param query: SQL query string with placeholders for params
    :param args: Tuple of args
    :param one: Return only first row if True
    :return Result as list of dicts (or single dict if one=True)
    '''
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Execute the query
        cur.execute(query, args)

        # Fetch column names / rows for dicts
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        result = [dict(zip(colnames, row)) for row in rows]

        # return first result if 'one' is True, else return all
        return (result[0] if result else None) if one else result
    except Exception as _e:
        # log exception here
        log.error(f"Database query failed: {_e}")
        return None
    finally:
        # ensure cursor and conn closed properly
        if conn is not None:
            conn.close()

def modify_db(query, args=(), fetch_id=False):
    '''
    Executes a specified INSERT/UPDATE/DELETE query (safely)
    :param query: SQL query string with placeholders for params
    :param args: Tuple of args
    :param fetch_id: Fetch ID of newly inserted/deleted row if necessary
    :return: Boolean indicating success/failure, entry_id (optional)
    '''
    conn = None
    entry_id = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # execute modification
        cur.execute(query, args)

        if fetch_id:
            entry_id = cur.fetchone()[0]

        conn.commit() # commit transaction to enable rolling back if something goes wrong
        
        success = True
    except Exception as _e:
        log.error(f"Database modification failed: {_e}")
        success = False
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return (success, entry_id) if fetch_id else (success,)

### CONFIGURATION FUNCTIONS
def write_config():
    '''Write configuration file to disk'''
    with open('config.yaml', 'w', encoding='UTF-8') as f:
        yaml.safe_dump(f, config.get_base())

### RESOURCES
### CREATE / READ / UPDATE / DELETE
class Feeds(Resource):
    '''API resource for aggregate feeds'''
    def get(self):
        '''Retrieve all feeds from database'''
        query = f'SELECT * FROM {SCHEMA}.feeds'
        feeds_data = query_db(query, args=None, one=False)
        return jsonify(feeds_data)

    def post(self):
        '''Add new feed'''
        # define fields
        required_fields = app_conf['database_defs']['feeds']['required']
        optional_fields = app_conf['database_defs']['feeds']['optional']

        # combine required + optional into valid field set
        valid_fields = set(required_fields + optional_fields)

        data = request.get_json()

        # required field check
        if not all(field in data for field in required_fields):
            return {'message': 'Missing required fields'}, 400

        # invalid field check
        if not all(key in valid_fields for key in data.keys()):
            return {'message': 'Invalid fields provided'}, 400

        # dynamically construct INSERT statement
        columns = list(data.keys())
        values = [data[key] for key in columns]
        columns_string = ', '.join(columns)
        placeholders_string = ', '.join(['%s'] + len(values))
        query = f"INSERT INTO {SCHEMA}.feeds ({columns_string}) \
            VALUES ({placeholders_string}) RETURNING id;"

        # execute the INSERT statement
        success, cur = modify_db(query, tuple(values), need_cursor=True)

        if success:
            new_feed_id = cur.fetchone()[0] if cur else None
            return {'message': 'feed added successfully', 'id': new_feed_id}, 201
        # else
        return {'message': 'failed to add feed'}, 500

class Feed(Resource):
    '''API resource for individual feeds'''
    def get(self, feed_id):
        '''Retrieve a specified feed'''
        # build query
        _query = f"SELECT * FROM {SCHEMA}.feeds WHERE id = %s"
        # execute query and return result
        feed_data = query_db(query=_query, args=(feed_id,), one=True)
        return jsonify(feed_data)

    def put(self, feed_id):
        '''Update a specfied feed'''
        update_data = request.get_json()

        # base query
        query_base = f"UPDATE {SCHEMA}.feeds SET "
        set_clauses = []
        query_values = []

        # dynamically construct SET portion of query
        for column, value in update_data.items():
            # for each col to update, add placeholder
            set_clauses.append(f"{column} = %s")
            query_values.append(value)

        # join the SET clauses and add WHERE
        query_set = ", ".join(set_clauses)
        query_where = " WHERE id = %s;"
        query_values.append(feed_id)

        # complete query
        query = query_base + query_set + query_where

        # execute query and return result
        result = modify_db(query, query_values)
        return result

    def delete(self, feed_id):
        '''Delete a specified feed'''
        # build base query
        query = f"DELETE FROM {SCHEMA}.feeds WHERE id = %s;"
        # execute query and return result
        result = modify_db(query, (feed_id,))
        return result

class Entries(Resource):
    '''API resource for aggregate entries'''
    def get(self):
        '''Retrieve all entries from database'''
        query = f'SELECT * FROM {SCHEMA}.rss_entries'
        entries_data = query_db(query, args=None, one=False)
        return jsonify(entries_data)

    def post(self):
        '''Add new entry'''
        # define fields
        required_fields = app_conf['database_defs']['entries']['required']
        optional_fields = app_conf['database_defs']['entries']['optional']

        # combine required + optional into valid field set
        valid_fields = set(required_fields + optional_fields)

        data = request.get_json()

        log.debug(data)

        # required field check
        if not all(field in data for field in required_fields):
            log.debug(f'POST entry error, missing required fields. Required: {required_fields}')
            log.debug(f'Provided: {data.keys()}')
            return {'message': 'Missing required fields.'}, 400

        # invalid field check
        if not all(key in valid_fields for key in data.keys()):
            return {'message': f'Invalid fields provided: {data.keys()}'}, 400

        # dynamically construct INSERT statement
        columns = list(data.keys())
        values = [data[key] for key in columns]
        columns_string = ', '.join(columns)
        placeholders_string = ', '.join(['%s'] * len(values))
        query = f"INSERT INTO {SCHEMA}.rss_entries ({columns_string}) \
            VALUES ({placeholders_string}) RETURNING id;"

        # execute the INSERT statement
        success, entry_id = modify_db(query, tuple(values), fetch_id=True)

        if success:
            return {'message': 'entry added successfully', 'id': entry_id}, 201
        # else
        return {'message': 'failed to add entry'}, 500

class Entry(Resource):
    '''API resource for individual entries'''
    def get(self, entry_id):
        '''Retrieve a specified entry'''
        # build query
        _query = f"SELECT * FROM {SCHEMA}.rss_entries WHERE id = %s"
        # execute query and return result
        entry_data = query_db(query=_query, args=(entry_id,), one=True)
        return jsonify(entry_data)

    def put(self, entry_id):
        '''Update a specfied entry'''
        update_data = request.get_json()

        # base query
        query_base = f"UPDATE {SCHEMA}.rss_entries SET "
        set_clauses = []
        query_values = []

        # dynamically construct SET portion of query
        for column, value in update_data.items():
            # for each col to update, add placeholder
            set_clauses.append(f"{column} = %s")
            query_values.append(value)

        # join the SET clauses and add WHERE
        query_set = ", ".join(set_clauses)
        query_where = " WHERE id = %s;"
        query_values.append(entry_id)

        # complete query
        query = query_base + query_set + query_where

        # execute query and return result
        result = modify_db(query, query_values)
        return result

    def delete(self, entry_id):
        '''Delete a specified entry'''
        # build base query
        query = f"DELETE FROM {SCHEMA}.rss_entries WHERE id = %s;"
        # execute query and return result
        result = modify_db(query, (entry_id,))
        return result

### OTHER
class FetchFeeds(Resource):
    '''Fetch all feeds'''
    def get(self):
        '''Send update request for all feeds to message queue'''
        query = f"SELECT * FROM {SCHEMA}.feeds WHERE status = true"
        # execute query and publish all feed data to queue
        feeds = query_db(query=query, args=None, one=False)
        for data in feeds:
            client.publish(OUT_KEY, data)
        return {"message": "initiated feeds update"}, 200

    def put(self):
        '''Send FORCED update for all feeds to queue'''
        query = f"SELECT * FROM {SCHEMA}.feeds WHERE status = true"
        # execute query and publish all feed data to queue
        feeds = query_db(query=query, args=None, one=False)
        for data in feeds:
            data['updated'] = "1970-01-01T00:00:00"
            client.publish(OUT_KEY, data)
        return {"message": "initiated (forced) feeds update"}, 200

class FetchFeed(Resource):
    '''Fetch specific feed'''
    def get(self, feed_id):
        '''Fetch specific feed'''
        _query = f"SELECT * FROM {SCHEMA}.feeds WHERE id = %s"
        # execute query and publish feed data to queue
        feed_data = query_db(query=_query, args=(feed_id,), one=True)
        client.publish(OUT_KEY, feed_data)
        return {"message": f"initiated update of feed: {feed_id}"}, 200

    def put(self, feed_id):
        '''Force fetch of specific feed'''
        _query = f"SELECT * FROM {SCHEMA}.feeds WHERE id = %s"
        # execute query and publish feed data to queue
        feed_data = query_db(query=_query, args=(feed_id,), one=True)
        feed_data['updated'] = "1970-01-01T00:00:00"
        client.publish(OUT_KEY, feed_data)
        return {"message": f"initiated update of feed: {feed_id}"}, 200

class HashCheck(Resource):
    '''Optimized resource for checking if entry already exists in database'''
    def get(self, entry_id):
        '''Existence check for entry in database'''
        _query = f"SELECT 1 FROM {SCHEMA}.rss_entries WHERE id = %s"
        exists = query_db(query=_query, args=(entry_id,), one=True)
        if exists:
            return None, 200
        return None, 404

class EntriesByFeed(Resource):
    '''Resource to retrieve entries from specified feed'''
    def get(self, feed_id):
        '''Retrieve all entries from a specified feed'''
        _query = f"SELECT * FROM {SCHEMA}.rss_entries WHERE feed = %s"
        data = query_db(query=_query, args=(feed_id,))
        return jsonify(data)

class UpdateConfig(Resource):
    '''Endpoint to manage configuration updates'''
    def get(self):
        '''Reload config and push "refresh" message to queue'''
        data = {'refresh': True}
        client.publish(OUT_KEY, data)
        config.reload_config()
        return {'message': 'initiated configuration update'}, 200

    def post(self):
        '''UNIMPLEMENTED - eventually use this to save config changes to file'''
        return {'message': 'unimplemnted'}, 404

### REPROCESS (UNIMPLEMENTED)
class ReprocessEntries(Resource):
    def get(self):
        '''UNIMPLEMENTED'''
        return {'message': 'unimplemnted'}, 404
class ReprocessEntry(Resource):
    def get(self):
        '''UNIMPLEMENTED'''
        return {'message': 'unimplemnted'}, 404

# PING (for healthcheck)
class Ping(Resource):
    def get(self):
        '''Ping endpoint for simple healthcheck'''
        return 'hello world', 200

def add_resources():
    '''Add resources to API instance'''
    # STANDARD CRUD OPERATIONS
    api.add_resource(Feeds, '/feeds')
    api.add_resource(Feed, '/feeds/<int:feed_id>')
    api.add_resource(Entries, '/entries')
    api.add_resource(Entry, '/entries/<int:entry_id>')

    # OTHER
    api.add_resource(FetchFeeds, '/fetch')
    api.add_resource(FetchFeed, '/fetch/<int:feed_id>')
    api.add_resource(HashCheck, '/entries/hash/<int:entry_id>')
    api.add_resource(EntriesByFeed, '/entries/f/<int:feed_id>')
    api.add_resource(UpdateConfig, '/update_config')
    api.add_resource(Ping, '/ping')

# ENV VARS / CONSTANTS
API_HOST = os.environ['API_HOST']
API_PORT = os.environ['API_PORT']
QUEUE_HOST = os.environ['QUEUE_HOST']
SCHEMA = os.environ['SCHEMA']
CONF_FILE = 'config.yaml'
OUT_KEY = "ingest"

# CONFIG SETUP
config = util.Config(CONF_FILE)
log = config.get_logger()
global_conf = config.get_subconfig(('global',))
app_conf = config.get_subconfig(('other', 'api'))

# Wait for RabbitMQ to wake up
time.sleep(int(global_conf['message-queue-delay']))
client = qclient.RabbitMQClient(host=QUEUE_HOST)

add_resources()

if __name__ == '__main__':
    while True:
        try:
            # Wait for database to respond before starting up
            get_db_connection()
            break
        except OperationalError as e:
            log.info("Database not responding yet. Sleeping...")
            time.sleep(30)
    app.run(host='0.0.0.0', port=API_PORT, debug=True)
