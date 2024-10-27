import websockets
import asyncio
import requests
import json
import re
import sys
import ssl
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

class ShowdownBot:
    def __init__(self, username, password, target_username):
        """
        Initialize the Pokemon Showdown bot with login credentials.
        
        Args:
            username (str): Pokemon Showdown registered username
            password (str): Pokemon Showdown account password
            target_username (str): Username to send test message to
        """
        self.ws = None
        self.username = username
        self.password = password
        self.target_username = target_username
        # Official Pokemon Showdown websocket server
        self.websocket_url = "wss://sim3.psim.us/showdown/websocket"
        
    async def connect(self):
        """
        Establish websocket connection to Pokemon Showdown server.
        Uses SSL context with verification disabled due to PS's self-signed cert.
        """
        try:
            print(f"Connecting to {self.websocket_url}...")
            # Create SSL context that accepts PS's self-signed certificate
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Establish websocket connection
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
        
    async def receive_messages(self):
        """
        Main message loop that receives messages from the server.
        Looks for the challstr needed for authentication and handles login.
        """
        try:
            while True:
                message = await self.ws.recv()
                print(f"Received: {message}")
                
                # Server sends challstr after connection - needed for login
                if "|challstr|" in message:
                    challstr = message.split("|challstr|")[1]
                    await self.login(challstr)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed unexpectedly")
            sys.exit(1)
        except Exception as e:
            print(f"Error receiving messages: {str(e)}")
            sys.exit(1)
                
    async def login(self, challstr):
        """
        Handles the login process for a registered account.
        
        The login flow works like this:
        1. Send credentials + challstr to PS login endpoint
        2. Get back an assertion token
        3. Send assertion token to the websocket to complete login
        
        Args:
            challstr (str): Challenge string received from server used for authentication
        """
        try:
            print("Attempting to login with registered account...")
            login_url = 'https://play.pokemonshowdown.com/action.php'
            
            # Prepare login data
            login_data = {
                'act': 'login',
                'name': self.username,
                'pass': self.password,
                'challstr': challstr
            }

            # Request authentication assertion from the login server
            response = requests.post(login_url, data=login_data)
            
            if response.status_code != 200:
                print(f"Login request failed with status {response.status_code}")
                sys.exit(1)
                
            # Response starts with ']', so we remove it before parsing JSON
            json_response = json.loads(response.text[1:])
            
            if not json_response.get('actionsuccess'):
                print("Login failed:", json_response.get('assertion', 'Unknown error'))
                sys.exit(1)
                
            assertion = json_response.get('assertion')
            
            # Send login command with assertion to the websocket
            login_cmd = f"|/trn {self.username},0,{assertion}"
            await self.ws.send(login_cmd)
            print(f"Logged in as {self.username}")
            
            # Send a test message to verify everything worked
            await asyncio.sleep(1)  # Brief pause to ensure login completed
            message = f"|/pm {self.target_username},Hello! I'm a test bot!"
            await self.ws.send(message)
            print(f"Sent test message to {self.target_username}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error during login request: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Error during login: {str(e)}")
            sys.exit(1)

    async def start(self):
        """
        Main entry point to start the bot.
        Connects to the server and starts listening for messages.
        """
        await self.connect()
        await self.receive_messages()

async def main():
    # Load credentials from environment variables
    USERNAME = os.getenv('PS_USERNAME')
    PASSWORD = os.getenv('PS_PASSWORD')
    TARGET_USERNAME = os.getenv('PS_TARGET_USERNAME', 'blueudon')
    
    # Verify environment variables are set
    if not USERNAME or not PASSWORD:
        print("Error: Please set PS_USERNAME and PS_PASSWORD environment variables")
        sys.exit(1)
    
    print(f"Starting bot with username: {USERNAME}")
    print(f"Will send test message to: {TARGET_USERNAME}")
    
    bot = ShowdownBot(USERNAME, PASSWORD, TARGET_USERNAME)
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")