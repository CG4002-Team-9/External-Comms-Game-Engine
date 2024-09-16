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

class QueuePurger:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None

    async def connect_rabbitmq(self):
        # Connect to RabbitMQ
        self.rabbitmq_connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=BROKERUSER,
            password=PASSWORD,
        )
        self.channel = await self.rabbitmq_connection.channel()
        print('[DEBUG] Connected to RabbitMQ')

    async def purge_queue(self, queue_name):
        # Get the queue object and purge it
        queue = await self.channel.declare_queue(queue_name, durable=True, passive=True)
        await queue.purge()
        print(f'[DEBUG] Purged queue: {queue_name}')

    async def run_purge(self):
        await self.connect_rabbitmq()
        # List of queues to purge
        queues_to_purge = ['ai_queue', 'update_eval_server_queue', 'update_ge_queue']
        for queue in queues_to_purge:
            await self.purge_queue(queue)
        # Close connection
        await self.rabbitmq_connection.close()
        print('[DEBUG] RabbitMQ connection closed after purging queues')

if __name__ == '__main__':
    purger = QueuePurger()
    asyncio.run(purger.run_purge())
