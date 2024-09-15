#!/usr/bin/env python

import asyncio
import json
import os
from dotenv import load_dotenv
import aio_pika

# Load environment variables from .env file
load_dotenv()

# RabbitMQ configurations
BROKER = os.getenv('BROKER')
BROKERUSER = os.getenv('BROKERUSER')
PASSWORD = os.getenv('PASSWORD')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))

# RabbitMQ queues
AI_QUEUE = 'ai_queue'
UPDATE_GE_QUEUE = 'update_ge_queue'

# Test data
TEST_IMU_DATA = {
    'length': 40,
    'ax': [1000] * 40,
    'ay': [2000] * 40,
    'az': [3000] * 40,
    'player_id': 1
}

class AITest:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.update_ge_queue = None

    async def setup_rabbitmq(self):
        # Connect to RabbitMQ
        self.connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=BROKERUSER,
            password=PASSWORD,
        )
        self.channel = await self.connection.channel()
        # Declare queues
        await self.channel.declare_queue(AI_QUEUE, durable=True)
        self.update_ge_queue = await self.channel.declare_queue(UPDATE_GE_QUEUE, durable=True)
        print('[DEBUG] Connected to RabbitMQ and declared queues')

    async def send_imu_data(self):
        # Publish test IMU data to ai_queue
        message_body = json.dumps(TEST_IMU_DATA).encode('utf-8')
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=AI_QUEUE,
        )
        print('[DEBUG] Published test IMU data to ai_queue')

    async def consume_update_ge_queue(self):
        # Consume messages from update_ge_queue
        async with self.update_ge_queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body.decode('utf-8'))
                    print(f'[DEBUG] Received message from update_ge_queue: {data}')
                    # Exit after receiving the message
                    return

    async def run_test(self):
        await self.setup_rabbitmq()
        # Send IMU data
        await self.send_imu_data()
        # Wait and consume message from update_ge_queue
        print('[DEBUG] Waiting for message from update_ge_queue...')
        await self.consume_update_ge_queue()
        # Close the connection
        await self.connection.close()

if __name__ == '__main__':
    test = AITest()
    asyncio.run(test.run_test())
