#!/usr/bin/env python

import asyncio
import json
import os
import socket
import sys
from dotenv import load_dotenv
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import aio_pika

# Load environment variables from .env file
load_dotenv()

BROKER = os.getenv('BROKER')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))

# For RabbitMQ
RABBITMQ_QUEUE = 'update_eval_server_queue'
UPDATE_GE_QUEUE = 'update_ge_queue'  # New queue for updating game engine


""" format of data passed to the eval_server
{
  "player_id": int,
  "action": str,
  "game_state": {
    "p1": {
      "hp": int,
      "bullets": int,
      "bombs": int,
      "shield_hp": int,
      "deaths": int,
      "shields": int
    },
    "p2": {
      "hp": int,
      "bullets": int,
      "bombs": int,
      "shield_hp": int,
      "deaths": int,
      "shields": int
    }
  }
}
"""


"""  format of data passed from the eval_server
{
  "p1": {
    "hp": int,
    "bullets": int,
    "bombs": int,
    "shield_hp": int,
    "deaths": int,
    "shields": int
  },
  "p2": {
    "hp": int,
    "bullets": int,
    "bombs": int,
    "shield_hp": int,
    "deaths": int,
    "shields": int
  }
}
"""

class EvalClient:
    def __init__(self, host, port, secret_key):
        self.host = host
        self.port = port
        self.secret_key = secret_key
        self.conn = None
        self.timeout = 2  # seconds
        self.loop = asyncio.get_event_loop()
        self.rabbitmq_connection = None
        self.channel = None
        self.queue = None
        self.update_ge_queue = None

    async def connect(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.settimeout(self.timeout)
        await self.loop.sock_connect(self.conn, (self.host, self.port))
        print(f'[DEBUG] Connected to evaluation server at {self.host}:{self.port}')

    async def send_text(self, text):
        cipher_text = self.encrypt_message(text)
        data = f"{len(cipher_text)}_{cipher_text}".encode('utf-8')
        await self.loop.sock_sendall(self.conn, data)
        print(f'[DEBUG] Sent encrypted text to server: {text}')

    def encrypt_message(self, message):
        secret_key = self.secret_key.encode('utf-8')
        iv = os.urandom(AES.block_size)
        cipher = AES.new(secret_key, AES.MODE_CBC, iv)
        padded_message = pad(message.encode('utf-8'), AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        encoded_message = base64.b64encode(iv + encrypted_message).decode('utf-8')
        return encoded_message

    async def recv_game_state(self):
        # Receive length followed by '_' followed by game_state JSON
        data = b''
        while not data.endswith(b'_'):
            chunk = await self.loop.sock_recv(self.conn, 1)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            data += chunk
        length = int(data[:-1])
        print(f'[DEBUG] Received game state length: {length}')
        game_state_data = b''
        while len(game_state_data) < length:
            chunk = await self.loop.sock_recv(self.conn, length - len(game_state_data))
            if not chunk:
                raise ConnectionError("Connection closed by server")
            game_state_data += chunk
        game_state_json = game_state_data.decode('utf-8')
        game_state = json.loads(game_state_json)
        print('[DEBUG] Received game_state from server:')
        print(json.dumps(game_state, indent=2))
        return game_state

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            print('[DEBUG] Closed connection to evaluation server')

    async def setup_rabbitmq(self):
        # Set up RabbitMQ connection using aio_pika
        print('[DEBUG] Connecting to RabbitMQ broker...')
        self.rabbitmq_connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=USERNAME,
            password=PASSWORD,
            loop=self.loop,
        )
        self.channel = await self.rabbitmq_connection.channel()
        # Set prefetch count to 0 to receive messages as they come
        await self.channel.set_qos(prefetch_count=0)
        # Declare the queue for receiving messages
        self.queue = await self.channel.declare_queue(RABBITMQ_QUEUE, durable=True)
        # Declare the update_ge_queue for publishing messages
        self.update_ge_queue = await self.channel.declare_queue(UPDATE_GE_QUEUE, durable=True)
        print(f'[DEBUG] Connected to RabbitMQ broker at {BROKER}')

    async def publish_to_update_ge_queue(self, message):
        # Publish message to update_ge_queue
        message_body = json.dumps(message).encode('utf-8')
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=UPDATE_GE_QUEUE,
        )
        print(f'[DEBUG] Published message to {UPDATE_GE_QUEUE}: {message}')

async def main():
    # Assume the server is running on localhost
    server_host = 'localhost'

    # The port number and secret key are provided as command-line arguments
    if len(sys.argv) < 3:
        print('Usage: eval_client.py <port_number> <secret_key>')
        sys.exit(1)
    port = int(sys.argv[1])
    secret_key = sys.argv[2]
    # Secret key must be 16 bytes long (AES-128)
    if len(secret_key) != 16:
        print('Secret key must be 16 characters long')
        sys.exit(1)

    eval_client = EvalClient(server_host, port, secret_key)
    try:
        await eval_client.connect()

        # Send 'hello' to verify password
        await eval_client.send_text('hello')
        print('[DEBUG] Sent verification message to server')

        # Set up RabbitMQ connection
        await eval_client.setup_rabbitmq()

        waiting_for_response_event = asyncio.Event()
        waiting_for_response_event.clear()  # Not waiting initially

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                if not waiting_for_response_event.is_set():
                    print('[DEBUG] Processing message from RabbitMQ queue')
                    action_data = json.loads(message.body.decode('utf-8'))
                    player_id = action_data['player_id']
                    action = action_data['action']
                    p1state = action_data['game_state']['p1']
                    p2state = action_data['game_state']['p2']
                    message_to_send = json.dumps({
                        'player_id': player_id,
                        'action': action,
                        'game_state': {
                            "p1": {
                            "hp": p1state['hp'],
                            "bullets": p1state['bullets'],
                            "bombs": p1state['bombs'],
                            "shield_hp": p1state['shield_hp'],
                            "deaths": p1state['deaths'],
                            "shields": p1state['shields']
                            },
                            "p2": {
                            "hp": p2state['hp'],
                            "bullets": p2state['bullets'],
                            "bombs": p2state['bombs'],
                            "shield_hp": p2state['shield_hp'],
                            "deaths": p2state['deaths'],
                            "shields": p2state['shields']
                            }
                        }
                    })
                    print(f'[DEBUG] Sending action and game_state to server: {message_to_send}')
                    await eval_client.send_text(message_to_send)
                    print('[DEBUG] Sent action and game_state to server')
                    waiting_for_response_event.set()
                    # Now wait for the response
                    try:
                        game_state = await eval_client.recv_game_state()
                        print('[DEBUG] Received response from server')
                        # After receiving response, publish to update_ge_queue
                        update_message = {
                            "update": True,
                            "game_state": game_state
                        }
                        await eval_client.publish_to_update_ge_queue(update_message)
                    except Exception as e:
                        print(f'[ERROR] Error receiving game state: {e}')
                    waiting_for_response_event.clear()
                else:
                    # Discard the message
                    print('[DEBUG] Discarding message from queue because waiting for response')

        # Start consuming messages
        await eval_client.queue.consume(on_message)
        print('[DEBUG] Started consuming messages from RabbitMQ queue')

        # Keep the program running
        await asyncio.Future()

    except Exception as e:
        print(f'[ERROR] {e}')
    finally:
        eval_client.close()

if __name__ == '__main__':
    asyncio.run(main())
