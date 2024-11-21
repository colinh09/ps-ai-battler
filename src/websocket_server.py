import json
import asyncio
import websockets
from system_manager import SystemManager
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WebSocketServer')

class BotWebSocketServer:
    def __init__(self):
        self.system_manager = None
        self.active_connections = set()
        load_dotenv()
        
        # Default credentials from environment variables
        self.default_credentials = {
            'username': os.getenv('PS_USERNAME'),
            'password': os.getenv('PS_PASSWORD'),
            'api_key': os.getenv('API_KEY')
        }

    async def handle_message(self, websocket, message):
        """Handle incoming messages from the Chrome extension"""
        try:
            data = json.loads(message)
            action = data.get('action')

            if action == 'startBot':
                settings = data.get('settings', {})
                response = await self.start_bot(settings)
            elif action == 'stopBot':
                response = await self.stop_bot()
            else:
                response = {'success': False, 'error': 'Unknown action'}

            await websocket.send(json.dumps(response))

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            await websocket.send(json.dumps({
                'success': False,
                'error': str(e)
            }))

    async def start_bot(self, settings):
        """Initialize and start the SystemManager with provided settings"""
        try:
            # Use default credentials if none provided
            username = settings.get('agentUsername') or self.default_credentials['username']
            password = settings.get('agentPassword') or self.default_credentials['password']
            target_username = settings.get('userUsername')
            personality = settings.get('personality', 'npc')

            if not target_username:
                return {'success': False, 'error': 'User username is required'}

            # Stop existing system manager if it exists
            if self.system_manager:
                await self.stop_bot()

            # Create new system manager
            self.system_manager = SystemManager(
                username=username,
                password=password,
                target_username=target_username,
                personality=personality
            )

            # Start in background task
            asyncio.create_task(self.system_manager.start())
            
            return {'success': True, 'message': 'Bot started successfully'}

        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def stop_bot(self):
        """Stop the current SystemManager instance"""
        try:
            if self.system_manager:
                await self.system_manager.quit()
                self.system_manager = None
            return {'success': True, 'message': 'Bot stopped successfully'}
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def handler(self, websocket):
        """Handle new WebSocket connections"""
        try:
            self.active_connections.add(websocket)
            async for message in websocket:
                await self.handle_message(websocket, message)
        finally:
            self.active_connections.remove(websocket)

    async def start_server(self, host='localhost', port=8765):
        """Start the WebSocket server"""
        async with websockets.serve(self.handler, host, port):
            logger.info(f"WebSocket server started on ws://{host}:{port}")
            await asyncio.Future()  # run forever

if __name__ == "__main__":
    server = BotWebSocketServer()
    asyncio.run(server.start_server())