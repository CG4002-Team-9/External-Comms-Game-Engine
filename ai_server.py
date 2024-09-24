#!/usr/bin/env python

import asyncio
import json
import os
from dotenv import load_dotenv
import aio_pika
from pynq import Overlay, allocate
import numpy as np

# Load environment variables from .env file
load_dotenv()

# Use the same broker, username, and password for RabbitMQ
BROKER = os.getenv('BROKER')
BROKERUSER = os.getenv('BROKERUSER')
PASSWORD = os.getenv('PASSWORD')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))

# RabbitMQ queues
AI_QUEUE = os.getenv('AI_QUEUE', 'ai_queue')  # Queue to consume messages from
UPDATE_GE_QUEUE = os.getenv("UPDATE_GE_QUEUE", "update_ge_queue")  # Queue to publish messages to

# Confidence threshold
CONFIDENCE_THRESHOLD = 0.94  # Adjust as needed

# Action mapping from index to action type
ACTION_MAPPING = {
    0: 'gun',
    1: 'shield',
    2: 'bomb',
    3: 'reload',
    4: 'basket',
    5: 'soccer',
    6: 'volley',
    7: 'bowl',
    8: '8',
    9: '9',
    10: '10',
    11: '11',
    12: '12',
    13: '13',
    14: '14',
    15: '15',
    16: '16',
    17: 'basket',
    18: '18',
    19: '19',
    # Add other mappings as per your model's output
}

class ActionClassifier:
    def __init__(self):
        folder_to_use = "./bitstream/"
        self.ol = Overlay(folder_to_use + 'design_1.bit')
        self.nn = self.ol.gesture_model_0
        self.nn.write(0x0, 0x81)
        self.dma = self.ol.axi_dma_0
        self.dma_send = self.dma.sendchannel
        self.dma_recv = self.dma.recvchannel
        self.input_stream = allocate(shape=(120,), dtype='float32')
        self.output_stream = allocate(shape=(20,), dtype='float32')  # Adjusted based on the model output size

    def predict(self, input_data):
        for i in range(120):
            self.input_stream[i] = input_data[i]

        self.dma_send.transfer(self.input_stream)
        self.dma_send.wait()

        self.dma_recv.transfer(self.output_stream)
        self.dma_recv.wait()

        # Assuming output_stream contains probabilities for each class
        action_index = np.argmax(self.output_stream)
        confidence = self.output_stream[action_index]

        return action_index, confidence

class AIServer:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None
        self.ai_queue = None
        self.classifier = ActionClassifier()

    async def setup_rabbitmq(self):
        # Set up RabbitMQ connection using aio_pika
        print('[DEBUG] Connecting to RabbitMQ broker...')
        self.rabbitmq_connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=BROKERUSER,
            password=PASSWORD,
        )
        self.channel = await self.rabbitmq_connection.channel()
        # Declare the ai_queue
        self.ai_queue = await self.channel.declare_queue(AI_QUEUE, durable=True)
        print(f'[DEBUG] Connected to RabbitMQ broker at {BROKER}:{RABBITMQ_PORT}')

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            print('[DEBUG] Received message from ai_queue')
            data = json.loads(message.body.decode('utf-8'))
            print(f'[DEBUG] Message content: {data}')
            return
            # Extract data
            length = data.get('length')
            ax = data.get('ax', [])
            ay = data.get('ay', [])
            az = data.get('az', [])
            player_id = data.get('player_id')

            # Check if data lengths match
            if length != len(ax) or length != len(ay) or length != len(az):
                print('[ERROR] Data lengths do not match')
                return

            # Normalize data to [-1, 1]
            max_value = 32767  # Max value for 16-bit signed integer
            input_data = np.array(ax + ay + az, dtype=np.float32) / max_value

            # Ensure input_data length is 120
            if len(input_data) != 120:
                print('[ERROR] Input data length is not 120')
                return

            # Run inference in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            try:
                action_index, confidence = await loop.run_in_executor(
                    None, self.classifier.predict, input_data)
                print(f'[DEBUG] Predicted action: {action_index}, confidence: {confidence}')
            except Exception as e:
                print(f'[ERROR] Error during inference: {e}')
                return

            # Check confidence threshold
            if confidence >= CONFIDENCE_THRESHOLD:
                # Map action index to action name
                action_type = ACTION_MAPPING.get(action_index, 'unknown')
                # Prepare message to send to update_ge_queue
                message_to_send = {
                    'action': True,
                    'player_id': player_id,
                    'action_type': action_type
                    # Include additional data if necessary
                }
                # Publish message to update_ge_queue
                message_body = json.dumps(message_to_send).encode('utf-8')
                await self.channel.default_exchange.publish(
                    aio_pika.Message(body=message_body),
                    routing_key=UPDATE_GE_QUEUE,
                )
                print(f'[DEBUG] Published message to {UPDATE_GE_QUEUE}: {message_to_send}')
            else:
                print('[DEBUG] Confidence below threshold, prediction discarded')

    async def run(self):
        await self.setup_rabbitmq()
        # Start consuming messages
        await self.ai_queue.consume(self.process_message)
        print('[DEBUG] Started consuming messages from ai_queue')
        # Keep the program running
        await asyncio.Future()

if __name__ == '__main__':
    ai_server = AIServer()
    try:
        asyncio.run(ai_server.run())
    except KeyboardInterrupt:
        print('[DEBUG] AI server stopped by user')
    except Exception as e:
        print(f'[ERROR] {e}')
