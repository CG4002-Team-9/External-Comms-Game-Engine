#!/usr/bin/env python

import asyncio
import json
import os
from dotenv import load_dotenv
import aio_pika

# Load environment variables from .env file
load_dotenv()

BROKER = os.getenv('BROKER')
BROKERUSER = os.getenv('BROKERUSER')
PASSWORD = os.getenv('PASSWORD')

RABBITMQ_QUEUE = 'update_eval_server_queue'

async def publish_message():
    print('[DEBUG] Connecting to RabbitMQ broker...')
    connection = await aio_pika.connect_robust(
        host=BROKER,
        port=5672,
        login=BROKERUSER,
        password=PASSWORD,
    )
    channel = await connection.channel()

    # Declare the queue
    await channel.declare_queue(RABBITMQ_QUEUE, durable=True)
    print(f'[DEBUG] Connected to RabbitMQ broker at {BROKER}')

    # Prepare a test message
    message = {
        'player_id': 1,
        'action': 'soccer',
        'game_state': {
            'p1': {
                'hp': 100,
                'bullets': 4,
                'bombs': 2,
                'shield_hp': 0,
                'deaths': 0,
                'shields': 3
            },
            'p2': {
                'hp': 70,
                'bullets': 6,
                'bombs': 2,
                'shield_hp': 0,
                'deaths': 0,
                'shields': 3
            }
        }
    }

    # Publish the message
    message_body = json.dumps(message).encode('utf-8')
    await channel.default_exchange.publish(
        aio_pika.Message(body=message_body),
        routing_key=RABBITMQ_QUEUE,
    )
    print('[DEBUG] Published test message to RabbitMQ queue')

    await connection.close()
    print('[DEBUG] Closed RabbitMQ connection')

if __name__ == '__main__':
    asyncio.run(publish_message())
