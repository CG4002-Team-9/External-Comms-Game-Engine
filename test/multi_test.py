#!/usr/bin/env python

import asyncio
import json
import os
import aio_pika

# Broker configurations
BROKER = os.getenv('BROKER', '178.128.213.67')
BROKERUSER = os.getenv('BROKERUSER', 'admin')
PASSWORD = os.getenv('PASSWORD', 'Team9Team')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))

class GameEngineTest:
    def __init__(self):
        self.rabbitmq_connection = None
        self.channel = None
        self.UPDATE_GE_QUEUE = 'update_ge_queue'
        self.UPDATE_EVERYONE_EXCHANGE = 'update_everyone_exchange'
        self.UPDATE_PREDICTIONS_EXCHANGE = 'update_predictions_exchange'
        self.update_everyone_exchange = None
        self.update_predictions_exchange = None

    async def setup_rabbitmq(self):
        # Connect to RabbitMQ
        self.rabbitmq_connection = await aio_pika.connect_robust(
            host=BROKER,
            port=RABBITMQ_PORT,
            login=BROKERUSER,
            password=PASSWORD,
        )
        self.channel = await self.rabbitmq_connection.channel()
        # Declare exchanges and queues
        await self.channel.declare_queue(self.UPDATE_GE_QUEUE, durable=True)
        self.update_everyone_exchange = await self.channel.declare_exchange(
            self.UPDATE_EVERYONE_EXCHANGE,
            aio_pika.ExchangeType.FANOUT,
            durable=True
        )
        self.update_predictions_exchange = await self.channel.declare_exchange(
            self.UPDATE_PREDICTIONS_EXCHANGE,
            aio_pika.ExchangeType.FANOUT,
            durable=True
        )
        print('[DEBUG] Connected to RabbitMQ and declared exchanges and queues')

    async def send_test_message(self, message, routing_key=None, exchange=None):
        # Publish message to given exchange or routing key
        message_body = json.dumps(message).encode('utf-8')
        if exchange:
            await exchange.publish(
                aio_pika.Message(body=message_body),
                routing_key=''
            )
            print(f'[DEBUG] Published message to exchange {exchange.name}: {message}')
        elif routing_key:
            await self.channel.default_exchange.publish(
                aio_pika.Message(body=message_body),
                routing_key=routing_key
            )
            print(f'[DEBUG] Published message to routing key {routing_key}: {message}')
        else:
            print('[ERROR] No exchange or routing key provided for sending message')

    def get_player_state_input(self):
        player_state = {}
        try:
            player_state['hp'] = int(input('Enter hp (integer): '))
            player_state['bullets'] = int(input('Enter bullets (integer): '))
            player_state['bombs'] = int(input('Enter bombs (integer): '))
            player_state['shield_hp'] = int(input('Enter shield_hp (integer): '))
            player_state['deaths'] = int(input('Enter deaths (integer): '))
            player_state['shields'] = int(input('Enter shields (integer): '))
        except ValueError:
            print('Invalid input. Please enter integer values.')
            return self.get_player_state_input()
        return player_state

    def get_visibility_input(self):
        visibility_info = {}
        opponent_visible_input = input('Is opponent visible? (yes/no): ').lower()
        visibility_info['opponent_visible'] = opponent_visible_input == 'yes'
        try:
            visibility_info['opponent_in_rain_bomb'] = int(input('Opponent in rain bomb count (integer): '))
        except ValueError:
            print('Invalid input. Please enter an integer value.')
            return self.get_visibility_input()
        return visibility_info

    async def run_test(self):
        await self.setup_rabbitmq()

        while True:
            # Get custom inputs from user
            player_id_input = input('Enter player ID (1 or 2) or type "no" to exit: ')
            if player_id_input.lower() == 'no':
                print('Exiting...')
                break

            try:
                player_id = int(player_id_input)
                if player_id not in [1, 2]:
                    print("Invalid player ID. Please enter 1 or 2.")
                    continue
            except ValueError:
                print("Invalid input. Please enter 1 or 2 or 'no' to exit.")
                continue

            # Provide action menu
            print('Select action:')
            print('(a) Simulate player action')
            print('(s) Send game state update')
            print('(v) Send visibility update')
            print('(p) Send prediction message')
            print('(l) Logout player')
            print('(u) Update evaluation server (not implemented)')
            print('(e) Exit')

            action_choice = input('Enter your choice: ').lower()

            if action_choice == 'e':
                print('Exiting...')
                break

            elif action_choice == 'a':
                # Simulate player action
                action_type = input('Enter action type (available: gun, soccer, basket, shield, volley, bomb, bowl, logout) or type "no" to cancel: ').lower()
                if action_type == 'no':
                    continue
                available_actions = ['gun', 'soccer', 'basket', 'shield', 'volley', 'bomb', 'bowl', 'logout', 'reload']
                if action_type not in available_actions:
                    print(f"Invalid action type. Please choose from {', '.join(available_actions)} or 'no' to cancel.")
                    continue
                hit_input = input('Did the action hit the opponent? (yes/no): ').lower()
                hit = hit_input == 'yes'
                # Construct message
                test_message = {
                    'action': True,
                    'player_id': player_id,
                    'action_type': action_type,
                    'hit': hit,
                    'game_state': {
                        'p1': {'opponent_visible': True, 'opponent_in_rain_bomb': 0},
                        'p2': {'opponent_visible': True, 'opponent_in_rain_bomb': 0}
                    }
                }
                # Send to update_ge_queue
                await self.send_test_message(test_message, routing_key=self.UPDATE_GE_QUEUE)

            elif action_choice == 's':
                # Send game state update
                print('Enter game state for player 1:')
                p1_state = self.get_player_state_input()
                print('Enter game state for player 2:')
                p2_state = self.get_player_state_input()
                test_message = {
                    'update': True,
                    'game_state': {
                        'p1': p1_state,
                        'p2': p2_state
                    }
                }
                # Send to update_everyone_exchange
                await self.send_test_message(test_message, exchange=self.update_everyone_exchange)

            elif action_choice == 'v':
                # Send visibility update
                print('Enter visibility info for player 1:')
                p1_visibility = self.get_visibility_input()
                print('Enter visibility info for player 2:')
                p2_visibility = self.get_visibility_input()
                test_message = {
                    'game_state': {
                        'p1': p1_visibility,
                        'p2': p2_visibility
                    }
                }
                # Send to update_everyone_exchange
                await self.send_test_message(test_message, exchange=self.update_everyone_exchange)

            elif action_choice == 'p':
                # Send prediction message
                action_type = input('Enter action type for prediction: ').lower()
                confidence_input = input('Enter confidence level (0.0 to 1.0): ')
                try:
                    confidence = float(confidence_input)
                    if not 0.0 <= confidence <= 1.0:
                        raise ValueError
                except ValueError:
                    print('Invalid confidence value. It should be a float between 0.0 and 1.0.')
                    continue
                test_message = {
                    'player_id': player_id,
                    'action_type': action_type,
                    'confidence': confidence
                }
                # Send to update_predictions_exchange
                await self.send_test_message(test_message, exchange=self.update_predictions_exchange)

            elif action_choice == 'l':
                # Logout player
                player_key = 'p1' if player_id == 1 else 'p2'
                test_message = {
                    'update': True,
                    'game_state': {
                        player_key: {
                            'login': False
                        }
                    }
                }
                # Send to update_everyone_exchange
                await self.send_test_message(test_message, exchange=self.update_everyone_exchange)

            elif action_choice == 'u':
                # Update evaluation server (not implemented)
                print('Update evaluation server functionality is not implemented in this test code.')
                continue

            else:
                print('Invalid choice. Please select a valid action.')
                continue

        # Close RabbitMQ connection after finishing
        await self.rabbitmq_connection.close()


if __name__ == '__main__':
    test = GameEngineTest()
    try:
        asyncio.run(test.run_test())
    except KeyboardInterrupt:
        print('Process interrupted. Exiting...')