#!/usr/bin/env python

import asyncio
import json
import os
from dotenv import load_dotenv
import aio_pika
import aiomqtt
import purge_queues

# Load environment variables from .env file
load_dotenv()

# Use the same broker, username, and password for both RabbitMQ and MQTT
BROKER = os.getenv('BROKER')
BROKERUSER = os.getenv('BROKERUSER')
PASSWORD = os.getenv('PASSWORD')

# Abstracted RabbitMQ port
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))

# RabbitMQ queues
UPDATE_EVAL_SERVER_QUEUE = os.getenv('UPDATE_EVAL_SERVER_QUEUE', 'update_eval_server_queue')
UPDATE_GE_QUEUE = os.getenv('UPDATE_GE_QUEUE', 'update_ge_queue') 

# RabbitMQ exchanges
UPDATE_EVERYONE_EXCHANGE = os.getenv('UPDATE_EVERYONE_EXCHANGE', 'update_everyone_exchange')

# Example full schema for messages to and from the game engine
"""
Schema for messages received from 'update_ge_queue' (from various sources):

{
  "update": true,                 # Indicates whether to send an update to all nodes
  "action": false,                # When true, perform calculations and update the game state
  "player_id": 1,                 # ID of the player performing the action
  "action_type": "gun",           # Type of action performed
  "hit": true,                    # For 'gun' action, indicates if the shot hit the target, need to make the distinction because gun can shoot without hitting the target (such as in eval server)  
  "game_state": {
    "p1": {
      "opponent_visible": false,
      "opponent_in_rain_bomb": 0,  # Counter for rain bombs affecting the player
      "disconnected": false,
      "login": true
    },
    "p2": {
      "opponent_visible": false,
      "opponent_in_rain_bomb": 0,
      "disconnected": false,
      "login": true
    }
  }
}

Schema for messages published to 'update_everyone' (to Nodes):

{
  "player_id": 1,
  "action": "gun",
  "game_state": { ... }  # Updated game state after calculations
}

Schema for messages published to 'update_eval_server_queue' (to Evaluation Server):

{
  "player_id": 1,
  "action": "gun",
  "game_state": { ... }  # Updated game state after calculations
}
"""

class GameEngine:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None
        self.update_ge_queue = None
        self.exchange = None
        self.update_everyone_queue = None
        # Initialize internal game state
        self.game_state = {
            'p1': {
                'hp': 100,
                'bullets': 6,
                'bombs': 2,
                'shield_hp': 0,
                'deaths': 0,
                'shields': 3,
                'opponent_hit': False, # Visualizer shows when opponent is damaged
                'opponent_shield_hit': False,  # Visualizer shows when opponent's shield is damaged
                'opponent_visible': True,
                'opponent_in_rain_bomb': 0,  # Counter for rain bombs
                'glove_connected': False,
                'vest_connected': False,
                'leg_connected': False,
                'login': True
            },
            'p2': {
                'hp': 100,
                'bullets': 6,
                'bombs': 2,
                'shield_hp': 0,
                'deaths': 0,
                'shields': 3,
                'opponent_hit': False,
                'opponent_shield_hit': False,  # Visualizer shows when opponent's shield is damaged
                'opponent_visible': True,
                'opponent_in_rain_bomb': 0,
                'glove_connected': False,
                'vest_connected': False,
                'leg_connected': False,
                'login': True
            }
        }

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
        # Declare the update_ge_queue
        self.update_ge_queue = await self.channel.declare_queue(UPDATE_GE_QUEUE, durable=True)
        
        self.exchange = await self.channel.declare_exchange(UPDATE_EVERYONE_EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
        print(f'[DEBUG] Connected to RabbitMQ broker at {BROKER}:{RABBITMQ_PORT}')

    async def publish_to_update_eval_server_queue(self, message):
        # Publish message to update_eval_server_queue
        message_body = json.dumps(message).encode('utf-8')
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=UPDATE_EVAL_SERVER_QUEUE,
        )
        print(f'[DEBUG] Published message to {UPDATE_EVAL_SERVER_QUEUE}: {json.dumps(message, indent = 2)}')

    def update_internal_game_state(self, incoming_game_state):
        # Update internal game state with the incoming data
        for player_key in ['p1', 'p2']:
            if player_key in incoming_game_state:
                self.game_state[player_key].update(incoming_game_state[player_key])

    def revive_player(self, player_id):
        player_key = f'p{player_id}'
        player = self.game_state[player_key]
        player['hp'] = 100
        player['deaths'] += 1
        player['shields'] = 3
        player['shield_hp'] = 0
        player['bullets'] = 6
        player['bombs'] = 2
        print(f'[DEBUG] Player {player_key[-1]} died and respawned.')
    
    def perform_damage(self, player_id, damage):
        player_key = f'p{player_id}'
        player = self.game_state[player_key]
        
        player_hit = False
        player_shield_hit = False
        
        # perform damage to shield first
        if player['shield_hp'] > 0:
            damage_to_shield = min(damage, player['shield_hp'])
            if damage_to_shield > 0:
                player_shield_hit = True
            player['shield_hp'] -= damage_to_shield
            damage -= damage_to_shield
            print(f'[DEBUG] Player {player_id}: Damage to shield: {damage_to_shield}. Shield HP left: {player["shield_hp"]}')
        
        # perform damage to HP
        if damage > 0:
            player_hit = True
            
        player['hp'] = max(0, player['hp'] - damage)
        print(f'[DEBUG] Player {player_id}: Damage to HP: {damage}. HP left: {player["hp"]}')
        if player['hp'] <= 0:
            self.revive_player(player_id)
        
        return player_hit, player_shield_hit
        
    
    def perform_action(self, player_id, action_type, data):
        # If either player is not logged in, do not perform any actions for both players
        if not self.game_state['p1']['login'] or not self.game_state['p2']['login']:
            print('[DEBUG] Cannot perform actions when one or both players are not logged in.')
            return False
        
        # Perform calculations based on action_type
        player_key = f'p{player_id}'
        opponent_key = 'p1' if player_key == 'p2' else 'p2'

        player = self.game_state[player_key]
        opponent = self.game_state[opponent_key]

        # Extract necessary data
        opponent_visible = player.get('opponent_visible', False)
        opponent_in_rain_bomb = player.get('opponent_in_rain_bomb', 0)
        hit = data.get('hit', False)

        opponent_hit = False
        opponent_shield_hit = False
        
        # Handle rain bomb damage
        if opponent_visible and opponent_in_rain_bomb > 0:
            for _ in range(opponent_in_rain_bomb):
                hit, shield_hit = self.perform_damage(opponent_key[-1], 5)
                opponent_hit = hit or opponent_hit
                opponent_shield_hit = shield_hit or opponent_shield_hit
                print(f'[DEBUG] Player {opponent_key[-1]}: Rain bomb damage: {5}')
        
        new_damage = 0
        
        # Handle actions
        if action_type == 'gun':
            #When player has ammo
            if player['bullets'] > 0:
                player['bullets'] -= 1
                if hit:
                    new_damage = 5
                print(f'[DEBUG] Player {player_id} fired a gun. Bullets left: {player["bullets"]}. Hit: {hit}')
        elif action_type == 'bomb':
            if player['bombs'] > 0 and opponent_visible:
                # Reduce bombs
                player['bombs'] -= 1
                print(f'[DEBUG] Player {player_id} threw a bomb. Bombs left: {player["bombs"]}')
                # Inflict immediate damage
                new_damage = 5
        elif action_type == 'reload':
            # Can only reload if bullets are zero
            if player['bullets'] == 0:
                player['bullets'] = 6
                print(f'[DEBUG] Player {player_id} reloaded. Bullets: {player["bullets"]}')
        elif action_type == 'shield':
            if player['shields'] > 0 and player['shield_hp'] == 0:
                # Reduce shields count
                player['shields'] -= 1
                # Reset shield HP
                player['shield_hp'] = 30
                print(f'[DEBUG] Player {player_id} activated a shield. Shields left: {player["shields"]}')
        elif action_type == 'logout':
            player['login'] = True
        elif action_type in ['basket', 'volley', "soccer", "bowl"]:
            # AI actions inflict damage only if opponent is visible
            if opponent_visible:
                new_damage = 10

        hit, shield_hit = self.perform_damage(opponent_key[-1], new_damage)
        opponent_hit = hit or opponent_hit
        opponent_shield_hit = shield_hit or opponent_shield_hit
        
        player['opponent_hit'] = opponent_hit
        player['opponent_shield_hit'] = opponent_shield_hit
        
        return True

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            print(f'[DEBUG] Received message from RabbitMQ queue "{UPDATE_GE_QUEUE}"')
            data = json.loads(message.body.decode('utf-8'))
            print(f'[DEBUG] Message content:\n{json.dumps(data, indent=2)}')

            action_performed = data.get("action", False)
            to_update = data.get("update", False)
            player_id = data.get('player_id')
            action_type = data.get('action_type')
            incoming_game_state = data.get('game_state', {})

            # Update internal game state with non-action-related info
            self.update_internal_game_state(incoming_game_state)

            # Hacky eval
            # self.game_state['p1']['opponent_visible'] = True
            # self.game_state['p2']['opponent_visible'] = True
            
            if action_performed:
                # Perform action calculations before updating internal state
                action_registered = self.perform_action(player_id, action_type, data)
                if not action_registered:
                  return
                
                # Prepare message to publish
                update_everyone_message = {
                    "game_state": self.game_state,
                    "action": action_type,
                    "player_id": player_id
                }
                update_everyone_message_string = json.dumps(update_everyone_message)
                # Publish to update_eval_server_queue
                await self.publish_to_update_eval_server_queue(update_everyone_message)
                
                # Publish to Exchange
                await self.exchange.publish(
                    aio_pika.Message(body=update_everyone_message_string.encode('utf-8')),
                    routing_key=''
                )
                print(f'[DEBUG] Published message to RabbitMQ exchange "{UPDATE_EVERYONE_EXCHANGE}": {json.dumps(update_everyone_message, indent = 2)}')
            elif to_update:
                # Prepare message to publish
                
                update_everyone_message = {
                    "game_state": self.game_state
                }
                update_everyone_message_string = json.dumps(update_everyone_message)
                # Publish to Exchange
                await self.exchange.publish(
                    aio_pika.Message(body=update_everyone_message_string.encode('utf-8')),
                    routing_key=''
                )
                print(f'[DEBUG] Published message to RabbitMQ exchange "{UPDATE_EVERYONE_EXCHANGE}": {json.dumps(update_everyone_message, indent = 2)}')
            else:
                # Only update internal game state without sending messages
                print(f'Game state updated internally: {json.dumps(self.game_state, indent=2)}')
                print('[DEBUG] Updated internal game state without sending any messages')
            
            # After doing any update, reset the opponent_hit and opponent_shield_hit flags
            self.game_state['p1']['opponent_hit'] = False
            self.game_state['p1']['opponent_shield_hit'] = False
            self.game_state['p2']['opponent_hit'] = False
            self.game_state['p2']['opponent_shield_hit'] = False

    async def run(self):
        # Create instance of QueuePurger and purge the queues before running the game engine
        purger = purge_queues.QueuePurger()
        print('[DEBUG] Purging queues before starting the game engine...')
        await purger.run_purge()  # Purge the queues
        
        # print the starting game state
        print(f'[DEBUG] Starting game state: {json.dumps(self.game_state, indent=2)}')
        
        await self.setup_rabbitmq()

        # Start consuming messages
        await self.update_ge_queue.consume(self.process_message)
        print(f'[DEBUG] Started consuming messages from {UPDATE_GE_QUEUE}')
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
