import websockets
import asyncio
import requests
import json
import re
import sys
import ssl
from dotenv import load_dotenv
import os
import random

class BattleState:
    def __init__(self):
        self.player1 = None
        self.player2 = None
        self.p1_team = []
        self.p2_team = []
        self.p1_active = None
        self.p2_active = None
        self.turn = 0
        self.weather = None
        self.terrain = None
        self.p1_conditions = {}  # Conditions like Reflect, Light Screen, etc.
        self.p2_conditions = {}
        
    def update_from_message(self, message):
        """Update battle state based on incoming message"""
        lines = message.split('\n')
        for line in lines:
            parts = line.split('|')
            if len(parts) < 2:
                continue
                
            command = parts[1]
            if command == 'player':
                player_num = parts[2]
                username = parts[3]
                if player_num == 'p1':
                    self.player1 = username
                else:
                    self.player2 = username
                    
            elif command == 'switch':
                position = parts[2][:3]  # p1a or p2a
                pokemon_data = parts[2].split(': ')[1]
                pokemon_name = pokemon_data.split(',')[0]
                hp_data = parts[3]
                
                if position == 'p1a':
                    self.p1_active = {
                        'name': pokemon_name,
                        'hp': hp_data,
                        'status': None,
                        'stats_changes': {}
                    }
                else:
                    self.p2_active = {
                        'name': pokemon_name,
                        'hp': hp_data,
                        'status': None,
                        'stats_changes': {}
                    }
                    
            elif command == 'turn':
                self.turn = int(parts[2])
                
            elif command == '-status':
                position = parts[2][:3]
                status = parts[3]
                if position == 'p1a':
                    self.p1_active['status'] = status
                else:
                    self.p2_active['status'] = status
                    
            elif command == '-boost' or command == '-unboost':
                position = parts[2][:3]
                stat = parts[3]
                amount = int(parts[4])
                if command == '-unboost':
                    amount = -amount
                    
                if position == 'p1a':
                    if stat not in self.p1_active['stats_changes']:
                        self.p1_active['stats_changes'][stat] = 0
                    self.p1_active['stats_changes'][stat] += amount
                else:
                    if stat not in self.p2_active['stats_changes']:
                        self.p2_active['stats_changes'][stat] = 0
                    self.p2_active['stats_changes'][stat] += amount
                    
    def get_state_summary(self):
        """Return a formatted summary of the current battle state"""
        summary = {
            'turn': self.turn,
            'player1': {
                'name': self.player1,
                'active_pokemon': self.p1_active,
                'conditions': self.p1_conditions
            },
            'player2': {
                'name': self.player2,
                'active_pokemon': self.p2_active,
                'conditions': self.p2_conditions
            },
            'weather': self.weather,
            'terrain': self.terrain
        }
        return summary

class ShowdownBot:
    def __init__(self, username, password, target_username):
        self.ws = None
        self.username = username
        self.password = password
        self.target_username = target_username
        self.websocket_url = "wss://sim3.psim.us/showdown/websocket"
        self.current_battle = None
        self.move_index = 0
        self.waiting_for_switch = False
        self.active_pokemon = None
        self.fainted_pokemon = set()
        self.battle_state = BattleState()
        
    async def connect(self):
        try:
            print(f"Connecting to {self.websocket_url}...")
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.ws = await websockets.connect(
                self.websocket_url,
                ping_interval=None,
                close_timeout=10,
                ssl=ssl_context
            )
            print("Connected successfully!")
        except Exception as e:
            print(f"Failed to connect: {str(e)}")
            sys.exit(1)

    async def get_user_choice(self, available_moves=None, available_switches=None):
        """Get user input for move or switch choice"""
        if available_moves:
            print("\nAvailable moves:")
            for i, move in enumerate(available_moves, 1):
                print(f"{i}: {move}")
                
        if available_switches:
            print("\nAvailable switches:")
            for i, pokemon in enumerate(available_switches, 1):
                print(f"Switch {i}: {pokemon}")
                
        while True:
            try:
                choice = input("\nEnter your choice (move 1-4 or switch 1-6): ").strip().lower()
                if choice.startswith('move '):
                    move_num = int(choice.split()[1])
                    if available_moves and 1 <= move_num <= len(available_moves):
                        return f"move {move_num}"
                elif choice.startswith('switch '):
                    switch_num = int(choice.split()[1])
                    if available_switches and 1 <= switch_num <= len(available_switches):
                        return f"switch {switch_num}"
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    async def handle_switch(self, request):
        """Handle switching Pokemon with user input"""
        if "side" in request and "pokemon" in request["side"]:
            available_pokemon = [
                (i + 1, pokemon["details"].split(',')[0])
                for i, pokemon in enumerate(request["side"]["pokemon"])
                if not pokemon.get("active", False) and 
                (i + 1) not in self.fainted_pokemon
            ]
            
            if available_pokemon:
                choice = await self.get_user_choice(available_switches=[p[1] for p in available_pokemon])
                if choice.startswith('switch '):
                    switch_position = int(choice.split()[1])
                    switch_cmd = f"{self.current_battle}|/choose switch {switch_position}"
                    await self.ws.send(switch_cmd)
                    self.active_pokemon = switch_position
                    return True
            else:
                print("No available Pokemon to switch to!")
                return False
        return False

    async def try_valid_move(self, request, active):
        """Try to execute a user-selected move"""
        if "moves" in active:
            moves = active["moves"]
            disabled_moves = set()
            
            if "trapped" in active:
                return False
                
            if "moveTrapped" in active:
                disabled_moves.update(i + 1 for i, move in enumerate(moves) if move.get("disabled"))
                
            available_moves = [
                (i + 1, move["move"])
                for i, move in enumerate(moves)
                if (i + 1) not in disabled_moves
            ]
            
            if available_moves:
                choice = await self.get_user_choice(available_moves=[m[1] for m in available_moves])
                if choice.startswith('move '):
                    move_num = int(choice.split()[1])
                    move_cmd = f"{self.current_battle}|/choose move {move_num}"
                    await self.ws.send(move_cmd)
                    return True
        return False

    async def handle_battle_message(self, room_id, message):
        """Handle messages from a battle room with state tracking"""
        try:
            # Update battle state
            self.battle_state.update_from_message(message)
            
            # Print current battle state at the start of each turn
            if "|turn|" in message:
                print("\nCurrent Battle State:")
                print(json.dumps(self.battle_state.get_state_summary(), indent=2))
            
            # Handle battle initialization
            if "|init|battle" in message:
                self.current_battle = room_id.strip('>')
                self.fainted_pokemon.clear()
                print(f"Joined battle room: {self.current_battle}")
                await self.ws.send(f"|/join {self.current_battle}")
                
            # Handle faint messages
            elif "|faint|" in message:
                fainted_pokemon = message.split("|faint|")[1].strip()
                if fainted_pokemon.startswith("p1a:"):  # If it's our Pokemon
                    print(f"Our Pokemon fainted: {fainted_pokemon}")
                    self.waiting_for_switch = True
                    if self.active_pokemon:
                        self.fainted_pokemon.add(self.active_pokemon)
                
            # Handle request for moves or switches
            elif "|request|" in message:
                request_data = message.split("|request|")[1].strip()
                if not request_data:
                    return
                    
                try:
                    request = json.loads(request_data)
                    
                    # Handle forced switches (from moves like U-turn or after fainting)
                    if "forceSwitch" in request and request["forceSwitch"][0]:
                        print("Forced switch required!")
                        if not await self.handle_switch(request):
                            print("No valid switches available!")
                        return
                        
                    # Handle regular moves when we have an active Pokemon
                    if "active" in request and request["active"]:
                        active = request["active"][0]
                        
                        # If waiting for switch and we have valid switches, do that first
                        if self.waiting_for_switch:
                            switched = await self.handle_switch(request)
                            if switched:
                                self.waiting_for_switch = False
                            return
                        
                        # If we're not waiting for a switch, try to make a move
                        if not self.waiting_for_switch:
                            await self.try_valid_move(request, active)
                            
                except json.JSONDecodeError as e:
                    print(f"Error parsing request JSON: {request_data}")
                    return
            
            # Handle turn starts
            elif "|turn|" in message:
                turn_num = message.split("|turn|")[1].strip()
                print(f"Turn {turn_num} started in {self.current_battle}")
                
            # Handle win message
            elif "|win|" in message:
                winner = message.split("|win|")[1].strip()
                print(f"Battle ended! Winner: {winner}")
                self.current_battle = None
                self.move_index = 0
                self.waiting_for_switch = False
                self.fainted_pokemon.clear()
                
            # Handle error messages
            elif "|error|" in message:
                error_msg = message.split("|error|")[1].strip()
                print(f"Received error: {error_msg}")
                if "Can't switch: You can't switch to a fainted Pokémon" in error_msg:
                    # Try another switch
                    await self.handle_switch(request)
                elif "Invalid choice" in error_msg:
                    # Try to make a different move or switch
                    if "active" in request and request["active"]:
                        active = request["active"][0]
                        if not await self.try_valid_move(request, active):
                            await self.handle_switch(request)
                
        except Exception as e:
            print(f"Error in handle_battle_message: {str(e)}")
            print(f"Message was: {message}")

    async def receive_messages(self):
        try:
            while True:
                message = await self.ws.recv()
                print(f"Received: {message}")
                
                if "|challstr|" in message:
                    challstr = message.split("|challstr|")[1]
                    await self.login(challstr)
                    await asyncio.sleep(2)
                    await self.challenge_player()
                
                elif message.startswith(">battle-"):
                    room_id = message.split("\n")[0]
                    await self.handle_battle_message(room_id, message)
                    
                elif "|error|" in message:
                    print(f"Received error: {message}")
                
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed unexpectedly")
            sys.exit(1)
        except Exception as e:
            print(f"Error receiving messages: {str(e)}")
            print(f"Message was: {message}")
            sys.exit(1)

    async def challenge_player(self):
        """Send a Random Battle challenge to the target player"""
        print(f"Challenging {self.target_username} to a Random Battle...")
        challenge_cmd = f"|/challenge {self.target_username}, gen9randombattle"
        await self.ws.send(challenge_cmd)
                
    async def login(self, challstr):
        try:
            print("Attempting to login with registered account...")
            login_url = 'https://play.pokemonshowdown.com/action.php'
            
            login_data = {
                'act': 'login',
                'name': self.username,
                'pass': self.password,
                'challstr': challstr
            }

            response = requests.post(login_url, data=login_data)
            
            if response.status_code != 200:
                print(f"Login request failed with status {response.status_code}")
                sys.exit(1)
                
            json_response = json.loads(response.text[1:])
            
            if not json_response.get('actionsuccess'):
                print("Login failed:", json_response.get('assertion', 'Unknown error'))
                sys.exit(1)
                
            assertion = json_response.get('assertion')
            
            login_cmd = f"|/trn {self.username},0,{assertion}"
            await self.ws.send(login_cmd)
            print(f"Logged in as {self.username}")
            
            await asyncio.sleep(1)
            message = f"|/pm {self.target_username},Hello! I'm a test bot! I'm going to challenge you to a Random Battle!"
            await self.ws.send(message)
            print(f"Sent test message to {self.target_username}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error during login request: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Error during login: {str(e)}")
            sys.exit(1)

    async def start(self):
        await self.connect()
        await self.receive_messages()

async def main():
    load_dotenv()
    USERNAME = os.getenv('PS_USERNAME')
    PASSWORD = os.getenv('PS_PASSWORD')
    TARGET_USERNAME = os.getenv('PS_TARGET_USERNAME', 'blueudon')
    
    if not USERNAME or not PASSWORD:
        print("Error: Please set PS_USERNAME and PS_PASSWORD environment variables")
        sys.exit(1)
    
    print(f"Starting bot with username: {USERNAME}")
    print(f"Will challenge: {TARGET_USERNAME}")
    
    bot = ShowdownBot(USERNAME, PASSWORD, TARGET_USERNAME)
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")