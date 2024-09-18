#!/usr/bin/env python

import asyncio
import json
import os
from dotenv import load_dotenv
import aio_pika
import aiomqtt

# Load environment variables from .env file
load_dotenv()

# Broker configurations
BROKER = os.getenv('BROKER')
BROKERUSER = os.getenv('BROKERUSER')
PASSWORD = os.getenv('PASSWORD')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))

# RabbitMQ queues
UPDATE_GE_QUEUE = 'update_ge_queue'
UPDATE_EVAL_SERVER_QUEUE = 'update_eval_server_queue'

# MQTT topic
MQTT_TOPIC_UPDATE_EVERYONE = 'update_everyone'

class GameEngineTest:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None
        self.update_eval_server_queue = None
        self.mqtt_client = None
        self.running = True  # Flag to control background tasks

    async def setup_rabbitmq(self):
        # Connect to RabbitMQ
        self.rabbitmq_connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=BROKERUSER,
            password=PASSWORD,
        )
        self.channel = await self.rabbitmq_connection.channel()
        # Declare queues
        await self.channel.declare_queue(UPDATE_GE_QUEUE, durable=True)
        self.update_eval_server_queue = await self.channel.declare_queue(UPDATE_EVAL_SERVER_QUEUE, durable=True)
        print('[DEBUG] Connected to RabbitMQ and declared queues')

    async def send_test_message(self, message):
        # Publish message to update_ge_queue
        message_body = json.dumps(message).encode('utf-8')
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=UPDATE_GE_QUEUE,
        )
        print(f'[DEBUG] Published test message to {UPDATE_GE_QUEUE}: {message}')

    async def consume_update_eval_server_queue(self):
        try:
            async with self.update_eval_server_queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        data = json.loads(message.body.decode('utf-8'))
                        print(f'[DEBUG] Received message from update_eval_server_queue: {data}')
                    if not self.running:
                        break
        except asyncio.CancelledError:
            print('[DEBUG] consume_update_eval_server_queue cancelled.')
            raise

    async def consume_mqtt_messages(self):
        try:
            async with self.mqtt_client.messages() as messages:
                await self.mqtt_client.subscribe(MQTT_TOPIC_UPDATE_EVERYONE, qos=2)
                async for message in messages:
                    payload = message.payload.decode('utf-8')
                    data = json.loads(payload)
                    print(f'[DEBUG] Received message from MQTT topic {MQTT_TOPIC_UPDATE_EVERYONE}: {data}')
                    await message.ack()
                    if not self.running:
                        break
        except asyncio.CancelledError:
            print('[DEBUG] consume_mqtt_messages cancelled.')
            raise

    async def run_test(self):
        await self.setup_rabbitmq()
        print('[DEBUG] Connecting to MQTT broker...')
        async with aiomqtt.Client(
            hostname=BROKER,
            port=MQTT_PORT,
            username=BROKERUSER,
            password=PASSWORD,
        ) as mqtt_client:
            self.mqtt_client = mqtt_client
            print('[DEBUG] Connected to MQTT broker')

            # Start background tasks for consuming messages
            self.running = True
            eval_server_task = asyncio.create_task(self.consume_update_eval_server_queue())
            mqtt_task = asyncio.create_task(self.consume_mqtt_messages())

            # Test cases
            test_messages = [
                {
                    'action': True,
                    'player_id': 1,
                    'action_type': 'gun',
                    'hit': True,  # Added 'hit' field
                    'game_state': {
                        'p1': {
                            },
                        'p2': {}
                    }
                },
                {
                    'action': True,
                    'player_id': 1,
                    'action_type': 'gun',
                    'hit': True,  # Added 'hit' field
                    'game_state': {
                        'p1': {
                            },
                        'p2': {}
                    }
                },
                {
                    'action': True,
                    'player_id': 1,
                    'action_type': 'gun',
                    'hit': True,  # Added 'hit' field
                    'game_state': {
                        'p1': {
                            },
                        'p2': {}
                    }
                },
                {
                    'action': True,
                    'player_id': 1,
                    'action_type': 'gun',
                    'hit': True,  # Added 'hit' field
                    'game_state': {
                        'p1': {
                            },
                        'p2': {}
                    }
                },
                {
                    'action': True,
                    'player_id': 1,
                    'action_type': 'gun',
                    'hit': True,  # Added 'hit' field
                    'game_state': {
                        'p1': {
                            },
                        'p2': {}
                    }
                },
                {
                    'action': True,
                    'player_id': 1,
                    'action_type': 'gun',
                    'hit': True,  # Added 'hit' field
                    'game_state': {
                        'p1': {
                            },
                        'p2': {}
                    }
                },
                {
                    'action': True,
                    'player_id': 2,
                    'action_type': 'shield',
                    'game_state': {
                        'p1': {},
                        'p2': {}
                    }
                },
                {
                    'game_state': {
                        'p1': {'opponent_visible': True},
                        'p2': {'opponent_visible': True}
                    }
                },
                {
                    # Case 3: Neither action nor update is True, should update internal state only
                    'action': True,
                    'player_id': 1,
                    'action_type': 'soccer',
                    'game_state': {
                        'p1': {},
                        'p2': {}
                    }
                },
                {
                    'game_state': {
                        'p1': {'opponent_visible': False},
                        'p2': {'opponent_visible': False}
                    }
                },
                {
                    # Case 3: Neither action nor update is True, should update internal state only
                    'action': True,
                    'player_id': 1,
                    'action_type': 'bowl',
                    'game_state': {
                        'p1': {},
                        'p2': {}
                    }
                },
                {
                    # Case 3: Neither action nor update is True, should update internal state only
                    'action': True,
                    'player_id': 1,
                    'action_type': 'volley',
                    'game_state': {
                        'p1': {},
                        'p2': {}
                    }
                },
                {
                    'game_state': {
                        'p1': {'opponent_visible': True},
                        'p2': {'opponent_visible': True}
                    }
                },
                {
                    # Case 3: Neither action nor update is True, should update internal state only
                    'action': True,
                    'player_id': 1,
                    'action_type': 'bomb',
                    'game_state': {
                        'p1': {},
                        'p2': {}
                    }
                },
                {
                    'game_state': {
                        'p1': {},
                        'p2': {'opponent_in_rain_bomb': 1}
                    }
                },
                {
                    # Case 3: Neither action nor update is True, should update internal state only
                    'action': True,
                    'player_id': 1,
                    'action_type': 'bomb',
                    'game_state': {
                        'p1': {},
                        'p2': {}
                    }
                },
                {
                    'game_state': {
                        'p1': {},
                        'p2': {'opponent_in_rain_bomb': 2}
                    }
                },
                {
                    'action': True,
                    'player_id': 1,
                    'action_type': 'gun',
                    'hit': True,  # Added 'hit' field
                    'game_state': {
                        'p1': {
                            },
                        'p2': {}
                    }
                },
            ]

            for test_case in test_messages:
                print(f'\n[DEBUG] Ready to send test message: {test_case}')
                user_input = input("Send message now? Y/n: ")
                if user_input.lower() == 'y':
                    await self.send_test_message(test_case)
                else:
                    print('[DEBUG] Skipping sending message.')
                # Allow time for messages to be processed
                await asyncio.sleep(1)

            # After sending all test messages, stop the background tasks
            self.running = False
            # Cancel background tasks
            eval_server_task.cancel()
            mqtt_task.cancel()
            try:
                await asyncio.gather(eval_server_task, mqtt_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

        # Close RabbitMQ connection
        await self.rabbitmq_connection.close()

if __name__ == '__main__':
    test = GameEngineTest()
    asyncio.run(test.run_test())
