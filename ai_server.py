#!/usr/bin/env python

import asyncio
import json
import os
from dotenv import load_dotenv
import aio_pika
from pynq import Overlay, allocate, PL
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import pickle
from sklearn.preprocessing import LabelEncoder

PL.reset()

folder_to_use = "./ai_folder/"

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

# RabbitMQ exchanges
UPDATE_PREDICTIONS_EXCHANGE = os.getenv("UPDATE_PREDICTIONS_EXCHANGE", "update_predictions_exchange")

# Confidence threshold
CONFIDENCE_THRESHOLD = 0.90  # Adjust as needed

TARGET_LENGTH_HAND = 59
INPUT_LENGTH_HAND = 354
OUTPUT_LENGTH_HAND = 10

TARGET_LENGTH_LEG = 40
INPUT_LENGTH_LEG = 240
OUTPUT_LENGTH_LEG = 4

# Load the saved LabelEncoder
with open(f'{folder_to_use}label_encoder.pkl', 'rb') as file:
    label_encoder_hand = pickle.load(file)
    
with open(f'{folder_to_use}label_encoder_leg.pkl', 'rb') as file:
    label_encoder_leg = pickle.load(file)

# Define the scaler to scale between -1 and 1 (to maintain negative values)
scaler = MinMaxScaler(feature_range=(-1, 1))

# Fit the scaler with the 16-bit signed integer range (this only needs to be done once)
scaler.fit(np.array([-2**15, 2**15 - 1]).reshape(-1, 1))

def pad_or_truncate(array, target_length=60):
    if len(array) > target_length:
        return array[:target_length]
    elif len(array) < target_length:
        return array + [0] * (target_length - len(array))
    else:
        return array

class ActionClassifier:
    def __init__(self):
        try:
            self.ol = Overlay(folder_to_use + 'new_unseen.bit')
            self.nn = self.ol.gesture_model_0
            self.nn.write(0x0, 0x81)
            self.dma = self.ol.axi_dma_0
            self.dma_send = self.dma.sendchannel
            self.dma_recv = self.dma.recvchannel
            self.input_stream_hand = allocate(shape=(INPUT_LENGTH_HAND + 1,), dtype='float32')
            self.output_stream_hand = allocate(shape=(OUTPUT_LENGTH_HAND,), dtype='float32')  # Adjusted based on the model output size
            self.input_stream_leg = allocate(shape=(INPUT_LENGTH_LEG + 1,), dtype='float32')
            self.output_stream_leg = allocate(shape=(OUTPUT_LENGTH_LEG,), dtype='float32')  # Adjusted based on the model output size
        except Exception as e:
            print(f'[ERROR] Initialization error: {e}')
            self.cleanup_buffers()
            raise

    def cleanup_buffers(self):
        """Free the allocated buffers to avoid memory issues."""
        try:
            if hasattr(self, 'input_stream_hand') and self.input_stream_hand is not None:
                self.input_stream_hand.freebuffer()
            if hasattr(self, 'output_stream_hand') and self.output_stream_hand is not None:
                self.output_stream_hand.freebuffer()
            if hasattr(self, 'input_stream_leg') and self.input_stream_leg is not None:
                self.input_stream_leg.freebuffer()
            if hasattr(self, 'output_stream_leg') and self.output_stream_leg is not None:
                self.output_stream_leg.freebuffer()
        except Exception as cleanup_error:
            print(f'[ERROR] Buffer cleanup error: {cleanup_error}')
    
    def __del__(self):
        """Ensure buffers are cleaned up when the object is deleted."""
        self.cleanup_buffers()
    
    def predict(self, input_data, device):
        try:
            if device == 'glove':
                self.input_stream = self.input_stream_hand
                self.output_stream = self.output_stream_hand
                self.input_stream[0] = 1.0
                for i in range(0, INPUT_LENGTH_HAND):
                    self.input_stream[i + 1] = input_data[i]
                    #print(f'[DEBUG] Input stream[{i + 1}]: {self.input_stream[i + 1]}')
            elif device == 'leg':
                self.input_stream = self.input_stream_leg
                self.output_stream = self.output_stream_leg
                self.input_stream[0] = 0
                for i in range(0, INPUT_LENGTH_LEG):
                    self.input_stream[i + 1] = input_data[i]
                    #print(f'[DEBUG] Input stream[{i + 1}]: {self.input_stream[i + 1]}')

            # print(f'[DEBUG] Input stream: {self.input_stream}')
            
            self.dma_send.transfer(self.input_stream)
            self.dma_send.wait()
            
            self.dma_recv.transfer(self.output_stream)
            self.dma_recv.wait()

            # Assuming output_stream contains probabilities for each class
            action_index = np.argmax(self.output_stream)
            confidence = self.output_stream[action_index]

            return action_index, confidence
        except Exception as e:
            print(f'[ERROR] Error during prediction: {e}')
            self.cleanup_buffers()
            raise
        
class AIServer:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None
        self.ai_queue = None
        self.exchange = None
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
        
        # Declare the exchange and queue 
        self.exchange = await self.channel.declare_exchange(UPDATE_PREDICTIONS_EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
        print(f'[DEBUG] Connected to RabbitMQ broker at {BROKER}:{RABBITMQ_PORT}')

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            
            print('[DEBUG] Received message from ai_queue')
            data = json.loads(message.body.decode('utf-8'))
            # print(f'[DEBUG] Message content: {data}')
            
            device = data.get('imu_device')
            
            if device == 'glove':
                target_length = TARGET_LENGTH_HAND
                input_length = INPUT_LENGTH_HAND
                output_length = OUTPUT_LENGTH_HAND
                label_encoder = label_encoder_hand
            elif device == 'leg':
                target_length = TARGET_LENGTH_LEG
                input_length = INPUT_LENGTH_LEG
                output_length = OUTPUT_LENGTH_LEG
                label_encoder = label_encoder_leg
            
            # Extract data
            ax = pad_or_truncate(data['ax'], target_length)
            ay = pad_or_truncate(data['ay'], target_length)
            az = pad_or_truncate(data['az'], target_length)
            gx = pad_or_truncate(data['gx'], target_length)
            gy = pad_or_truncate(data['gy'], target_length)
            gz = pad_or_truncate(data['gz'], target_length)
            player_id = data.get('player_id')

            # Normalize data to [-1, 1]
            # Concatenate all six arrays (ax, ay, az, gx, gy, gz)
            imu_data = ax + ay + az + gx + gy + gz
            # print("IMU Data:", imu_data)  # Sanity check
            imu_data = np.array(imu_data).reshape(-1, 1)  # Reshape for the scaler
            
            # Scale the data
            input_data = scaler.transform(imu_data).flatten()
            # print("input_data Data:", input_data)  # Sanity check
            # print("input_data Data Length:", len(input_data))  # Sanity check
            
            # Ensure input_data length is correct
            if len(input_data) != input_length:
                print(f'[ERROR] Input data length is not {input_length}')
                return

            # Run inference in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            try:
                action_index, confidence = await loop.run_in_executor(
                    None, self.classifier.predict, input_data, device)
                action_type = label_encoder.inverse_transform([action_index])[0]
                print(f'[DEBUG] Predicted action: {action_type}, confidence: {confidence}')
            except Exception as e:
                print(f'[ERROR] Error during inference: {e}')
                return

            # Check confidence threshold
            if confidence >= CONFIDENCE_THRESHOLD:
                # Map action index to action name
                if action_type not in ['basket', 'bowl', 'volley', 'soccer', 'reload', 'logout', 'shield', 'bomb']:
                    print(f'[ERROR] Invalid action type: {action_type}')
                else:
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
            
            update_predictions_message = {
                "player_id": player_id,
                "action_type": action_type,
                "confidence": float(confidence)
            }
            
            update_predictions_string = json.dumps(update_predictions_message)
            
            await self.exchange.publish(
                aio_pika.Message(body=update_predictions_string.encode('utf-8')),
                routing_key=''
            )
            print(f'[DEBUG] Published message to RabbitMQ exchange "{UPDATE_PREDICTIONS_EXCHANGE}": {json.dumps(update_predictions_message, indent = 2)}')
            
            

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
        ai_server.classifier.cleanup_buffers()  # Ensure buffers are cleared on manual stop
    except Exception as e:
        print(f'[ERROR] {e}')
        ai_server.classifier.cleanup_buffers()  # Ensure buffers are cleared on manual stop
