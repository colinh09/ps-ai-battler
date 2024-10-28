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

# Load environment variables from .env file
load_dotenv()

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

    async def handle_switch(self, request):
        """Handle switching Pokemon"""
        if "side" in request and "pokemon" in request["side"]:
            available_pokemon = [
                i + 1 for i, pokemon in enumerate(request["side"]["pokemon"])
                if not pokemon.get("active", False) and not pokemon.get("fainted", False)
            ]
            
            if available_pokemon:
                # Choose a random available Pokemon
                switch_position = random.choice(available_pokemon)
                print(f"Switching to Pokemon in position {switch_position}")
                switch_cmd = f"{self.current_battle}|/choose switch {switch_position}"
                await self.ws.send(switch_cmd)
                return True
        return False

    async def handle_battle_message(self, room_id, message):
        """Handle messages from a battle room"""
        try:
            # Handle battle initialization
            if "|init|battle" in message:
                self.current_battle = room_id.strip('>')
                print(f"Joined battle room: {self.current_battle}")
                await self.ws.send(f"|/join {self.current_battle}")
                
            # Handle faint messages
            elif "|faint|" in message:
                fainted_pokemon = message.split("|faint|")[1].strip()
                print(f"Pokemon fainted: {fainted_pokemon}")
                self.waiting_for_switch = True
                
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
                        await self.handle_switch(request)
                        return
                        
                    # Handle regular moves when we have an active Pokemon
                    if "active" in request and request["active"]:
                        # If waiting for switch and we have valid switches, do that first
                        if self.waiting_for_switch:
                            switched = await self.handle_switch(request)
                            if switched:
                                self.waiting_for_switch = False
                                return
                                
                        active = request["active"][0]
                        if "moves" in active:
                            moves = active["moves"]
                            move_num = (self.move_index % len(moves)) + 1
                            self.move_index += 1
                            print(f"Choosing move {move_num} in {self.current_battle}")
                            move_cmd = f"{self.current_battle}|/choose move {move_num}"
                            print(f"Sending command: {move_cmd}")
                            await self.ws.send(move_cmd)
                            
                except json.JSONDecodeError as e:
                    print(f"Error parsing request JSON: {request_data}")
                    return
            
            # Handle turn starts
            elif "|turn|" in message:
                turn_num = message.split("|turn|")[1].strip()
                print(f"Turn {turn_num} started in {self.current_battle}")
                self.waiting_for_switch = False  # Reset switch flag at start of turn
            
            elif "|win|" in message:
                winner = message.split("|win|")[1].strip()
                print(f"Battle ended! Winner: {winner}")
                self.current_battle = None
                self.move_index = 0
                self.waiting_for_switch = False
                
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