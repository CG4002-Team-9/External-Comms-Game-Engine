#!/usr/bin/env python

import asyncio
import os
from dotenv import load_dotenv
import aio_pika

# Load environment variables from .env file
load_dotenv()

# Broker configurations
BROKER = os.getenv('BROKER')
BROKERUSER = os.getenv('BROKERUSER')
PASSWORD = os.getenv('PASSWORD')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))

UPDATE_EVAL_SERVER_QUEUE = os.getenv('UPDATE_EVAL_SERVER_QUEUE', 'update_eval_server_queue')
UPDATE_GE_QUEUE = os.getenv('UPDATE_GE_QUEUE', 'update_ge_queue') 
AI_QUEUE = os.getenv('AI_QUEUE', 'ai_queue')

class QueuePurger:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None

    async def connect_rabbitmq(self):
        # Connect to RabbitMQ with increased timeout
        self.rabbitmq_connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=BROKERUSER,
            password=PASSWORD,
            timeout=30  # Increase timeout
        )
        self.channel = await self.rabbitmq_connection.channel()
        print('[DEBUG] Connected to RabbitMQ')

    async def declare_or_create_queue(self, queue_name):
        try:
            # Try to declare the queue passively (check if it exists)
            await self.channel.declare_queue(queue_name, durable=True, passive=True)
            print(f'[DEBUG] Queue "{queue_name}" exists.')
        except aio_pika.exceptions.ChannelClosed as e:
            print(f'[DEBUG] Queue "{queue_name}" does not exist. Creating queue...')
            try:
                # Attempt to create a durable queue
                await self.channel.declare_queue(queue_name, durable=True)
                print(f'[DEBUG] Queue "{queue_name}" created.')
            except Exception as create_exception:
                print(f'[ERROR] Failed to create queue "{queue_name}": {create_exception}')
        except Exception as ex:
            print(f'[ERROR] Unexpected error declaring queue "{queue_name}": {ex}')

    async def purge_queue(self, queue_name):
        await self.declare_or_create_queue(queue_name)
        queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.purge()
        print(f'[DEBUG] Purged queue: {queue_name}')

    async def run_purge(self):
        await self.connect_rabbitmq()
        # List of queues to check and purge
        queues_to_purge = [UPDATE_EVAL_SERVER_QUEUE, UPDATE_GE_QUEUE, AI_QUEUE]
        for queue in queues_to_purge:
            await self.purge_queue(queue)
        await self.rabbitmq_connection.close()
        print('[DEBUG] RabbitMQ connection closed after purging queues')

if __name__ == '__main__':
    purger = QueuePurger()
    asyncio.run(purger.run_purge())
