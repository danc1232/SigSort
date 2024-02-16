'''Module that implements simple RabbitMQ client'''
import json
import time
from datetime import datetime
import pika
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker, \
    ConnectionClosedByBroker, StreamLostError, ChannelWrongStateError

class CustomJSONEncoder(json.JSONEncoder):
    '''Custom JSON encoder to automatically handle datetime serialization'''
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

class RabbitMQClient:
    '''Client to handle creation of connections, channels, and messaging functions for RabbitMQ'''
    def __init__(self, host, heartbeat=600, blocked_connection_timeout=300):
        self.host = host
        self.heartbeat = heartbeat
        self.blocked_connection_timeout = blocked_connection_timeout
        self.connection_params = pika.ConnectionParameters(
            host=self.host,
            heartbeat=self.heartbeat,
            blocked_connection_timeout=self.blocked_connection_timeout,
            credentials=pika.PlainCredentials('user', 'password')
        )
        self.connection = None
        self.channel = None
        self.connect()

    def connect(self):
        '''Establish a connection to RabbitMQ.'''
        try:
            self.close()
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()
            self.channel.confirm_delivery()  # Optional: Enables delivery confirmations
        except AMQPConnectionError as e:
            print(f"Connection to RabbitMQ failed: {e}")
            time.sleep(10)  # Wait before retrying
            self.connect()  # Retry connection
        except Exception as e:
            raise e

    def check_connection(self):
        '''Check if the connection and channel are open and reconnect if necessary.'''
        if self.connection is None or not self.connection.is_open or \
            self.channel is None or not self.channel.is_open:
            self.connect()

    def publish(self, key, message):
        '''Publish a message to a specified queue with automatic reconnection.'''
        try:
            self.check_connection()
            self.channel.queue_declare(queue=key, durable=True)
            self.channel.basic_publish(
                exchange='',
                routing_key=key,
                body=json.dumps(message, cls=CustomJSONEncoder),
                properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
            )
            # useful for debugging
            # print(f"Message published to queue {key}")
        except (ChannelClosedByBroker, ConnectionClosedByBroker, StreamLostError, ChannelWrongStateError) as e:
            print(f"Publish error: {e}")
            self.connect()
            self.publish(key, message)  # Retry publishing after reconnection
        except Exception as e:
            print(f"Unrecognized error: {e}")
            self.connect()
            self.publish(key, message)  # Retry publishing after reconnection

    def consume(self, key, callback):
        '''Start consuming messages from a specified queue with automatic reconnection.'''
        self.check_connection()
        try:
            self.channel.queue_declare(queue=key, durable=True)
            self.channel.basic_qos(prefetch_count=20)
            self.channel.basic_consume(queue=key, on_message_callback=callback, auto_ack=False)
            print(f"Starting to consume from queue {key}")
            self.channel.start_consuming()
        except (ChannelClosedByBroker, ConnectionClosedByBroker, \
                StreamLostError, ChannelWrongStateError) as e:
            print(f"Consume error: {e}")
            self.connect()
            self.consume(key, callback)  # Retry consuming after reconnection

    def close(self):
        '''Close the RabbitMQ connection.'''
        if self.channel is not None and self.channel.is_open:
            self.channel.close()
        if self.connection is not None and self.connection.is_open:
            self.connection.close()
