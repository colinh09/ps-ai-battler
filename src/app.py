from flask import Flask, request, jsonify
from system_manager import SystemManager
import os
from dotenv import load_dotenv
import asyncio
from functools import partial
import threading

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Global dict to store active system managers
active_bots = {}

def run_async_task(coro):
    """Helper function to run coroutines in the background"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/api/start', methods=['POST'])
def start_bot():
    try:
        data = request.get_json()
        
        if not data or 'userUsername' not in data:
            return jsonify({
                'success': False,
                'error': 'User username is required'
            }), 400
            
        # Get defaults from environment variables
        default_username = os.getenv('PS_USERNAME')
        default_password = os.getenv('PS_PASSWORD')
        
        # Use provided settings or defaults
        username = data.get('agentUsername') or default_username
        password = data.get('agentPassword') or default_password
        target_username = data['userUsername']  # Required field
        personality = data.get('personality', 'npc')
        
        # Create unique key for this bot instance
        bot_key = f"{username}_{target_username}"
        
        # Stop existing bot for this user if it exists
        if bot_key in active_bots:
            run_async_task(active_bots[bot_key].quit())
            del active_bots[bot_key]
        
        # Create new system manager
        system = SystemManager(
            username=username,
            password=password,
            target_username=target_username,
            personality=personality
        )
        
        # Store the system manager
        active_bots[bot_key] = system
        
        # Start the bot in a background thread
        def run_bot():
            run_async_task(system.start())
            
        thread = threading.Thread(target=run_bot)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Bot started for user {target_username}',
            'bot_key': bot_key
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    try:
        data = request.get_json()
        
        if not data or ('userUsername' not in data and 'bot_key' not in data):
            return jsonify({
                'success': False,
                'error': 'Either userUsername or bot_key is required'
            }), 400
            
        # Try to find bot by key first
        bot_key = data.get('bot_key')
        if not bot_key:
            # Construct key from username
            username = data.get('agentUsername', os.getenv('PS_USERNAME'))
            target_username = data['userUsername']
            bot_key = f"{username}_{target_username}"
            
        if bot_key not in active_bots:
            return jsonify({
                'success': False,
                'error': 'No active bot found for this user'
            }), 404
            
        system = active_bots[bot_key]
        system.is_running = False
        if system.battle_manager:
            system.battle_manager.is_running = False 
            if system.battle_manager.bot:
                system.battle_manager.bot.is_running = False
        if system.bot:
            system.bot.is_running = False
            
        run_async_task(system.quit())
        del active_bots[bot_key]
        
        return jsonify({
            'success': True,
            'message': f'Bot stopped successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)