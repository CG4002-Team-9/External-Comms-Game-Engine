#!/usr/bin/env python

import asyncio
import json
import os
from dotenv import load_dotenv
import aio_pika
import aiomqtt  # Updated import

# Load environment variables from .env file
load_dotenv()

# Use the same broker, username, and password for both RabbitMQ and MQTT
BROKER = os.getenv('BROKER')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# Abstracted RabbitMQ port
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))

# MQTT broker settings (same as RabbitMQ)
MQTT_BROKER = BROKER
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))

# RabbitMQ queues
UPDATE_GE_QUEUE = 'update_ge_queue'
UPDATE_EVAL_SERVER_QUEUE = 'update_eval_server_queue'  # Queue to publish to when action is true

# MQTT topic
MQTT_TOPIC_UPDATE_EVERYONE = 'update_everyone'

# Example full schema for messages to and from the game engine
"""
Schema for messages received from 'update_ge_queue' (from Evaluation Client):

{
  "update": true,
  "action": false,                  # When true, calculate new state based on action and update game state, and send to eval server.
  "player_id": 1,
  "action_type": "gun",
  "game_state": {
    "p1": {
      "hp": 100,
      "bullets": 6,
      "bombs": 2,
      "shield_hp": 30,
      "deaths": 0,
      "shields": 3
    },
    "p2": {
      "hp": 95,
      "bullets": 5,
      "bombs": 1,
      "shield_hp": 20,
      "deaths": 1,
      "shields": 2
    }
  }
}

Schema for messages published to 'update_everyone' (to Nodes) and 'update_eval_server_queue' (to Evaluation Server):

{
  "player_id": 1,
  "action": "gun",
  "game_state": {
    "p1": {
      "hp": 100,
      "bullets": 6,
      "bombs": 2,
      "shield_hp": 30,
      "deaths": 0,
      "shields": 3
    },
    "p2": {
      "hp": 95,
      "bullets": 5,
      "bombs": 1,
      "shield_hp": 20,
      "deaths": 1,
      "shields": 2
    }
  }
}
"""

class GameEngine:
    def __init__(self):
        # Removed self.loop
        self.rabbitmq_connection = None
        self.channel = None
        self.update_ge_queue = None
        self.mqtt_client = None

    async def setup_rabbitmq(self):
        # Set up RabbitMQ connection using aio_pika
        print('[DEBUG] Connecting to RabbitMQ broker...')
        self.rabbitmq_connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=USERNAME,
            password=PASSWORD,
            # Removed loop parameter
        )
        self.channel = await self.rabbitmq_connection.channel()
        # Declare the update_ge_queue
        self.update_ge_queue = await self.channel.declare_queue(UPDATE_GE_QUEUE, durable=True)
        print(f'[DEBUG] Connected to RabbitMQ broker at {BROKER}:{RABBITMQ_PORT}')

    async def publish_to_update_eval_server_queue(self, message):
        # Publish message to update_eval_server_queue
        message_body = json.dumps(message).encode('utf-8')
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=UPDATE_EVAL_SERVER_QUEUE,
        )
        print(f'[DEBUG] Published message to {UPDATE_EVAL_SERVER_QUEUE}: {message}')

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            print('[DEBUG] Received message from update_ge_queue')
            data = json.loads(message.body.decode('utf-8'))
            print(f'[DEBUG] Message content: {data}')

            # Perform appropriate calculations (dummy calculations in this example)
            # For this example, we'll assume calculations are done and proceed to check flags

            action_performed = data.get("action", False)
            to_update = data.get("update", False)
            
            # if update is true, update all the nodes
            # if action is true, update the eval_server after calculations
            # if both not true, update the information without calculation (visibility)
            
            # Prepare message to publish to MQTT topic update_everyone
            mqtt_message = {
                "game_state": data.get('game_state', {}),
                "action": data.get('action_type', None),
                "player_id": data.get('player_id', None)
            }
            # Publish to MQTT topic with QoS level 2
            mqtt_message_str = json.dumps(mqtt_message)
            await self.mqtt_client.publish(
                MQTT_TOPIC_UPDATE_EVERYONE,
                mqtt_message_str.encode('utf-8'),
                qos=2  # Ensure QoS level 2 for guaranteed delivery
            )
            print(f'[DEBUG] Published message to MQTT topic {MQTT_TOPIC_UPDATE_EVERYONE}: {mqtt_message}')

            if data.get('action', False):
                # If 'action' is True, publish to update_eval_server_queue
                await self.publish_to_update_eval_server_queue(mqtt_message)

    async def run(self):
        await self.setup_rabbitmq()

        # Set up MQTT client using aiomqtt
        print('[DEBUG] Connecting to MQTT broker...')
        
        async with aiomqtt.Client(
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            username=USERNAME,
            password=PASSWORD
        ) as self.mqtt_client:
            print(f'[DEBUG] Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}')
            
            # Start consuming messages
            await self.update_ge_queue.consume(self.process_message)
            print('[DEBUG] Started consuming messages from update_ge_queue')

            # Keep the program running
            await asyncio.Future()


if __name__ == '__main__':
    game_engine = GameEngine()
    try:
        asyncio.run(game_engine.run())
    except KeyboardInterrupt:
        print('[DEBUG] Game engine stopped by user')
    except Exception as e:
        print(f'[ERROR] {e}')
