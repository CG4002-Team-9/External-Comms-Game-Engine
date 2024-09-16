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

class GameEngineTest:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None
        self.update_eval_server_queue = None
        self.mqtt_client = None

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
        print('[DEBUG] Connected to RabbitMQ and declared queues')

    async def send_test_message(self, message):
        # Publish message to update_ge_queue
        message_body = json.dumps(message).encode('utf-8')
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=UPDATE_GE_QUEUE,
        )
        print(f'[DEBUG] Published test message to {UPDATE_GE_QUEUE}: {message}')

    async def run_test(self):
        await self.setup_rabbitmq()

        # Test case to be sent
        test_message = {
            'action': True,
            'player_id':1,
            'action_type': 'bomb',
            'hit': True,  # Added 'hit' field
            'game_state': {
                'p1': {'opponent_visible': True,
                       'opponent_in_rain_bomb': 0},
                'p2': {'opponent_visible': True,
                       'opponent_in_rain_bomb': 0}
            }
        }

        # Send the single test message
        await self.send_test_message(test_message)

        # Close RabbitMQ connection after sending the message
        await self.rabbitmq_connection.close()

if __name__ == '__main__':
    test = GameEngineTest()
    asyncio.run(test.run_test())
