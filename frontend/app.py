from flask import Flask, render_template, request, jsonify
import sys
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from datetime import datetime
import json
import asyncio
import threading

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from system_manager import SystemManager

app = Flask(__name__)

# Global variables
system = None
background_loop = None

@dataclass
class ChatMessage:
    content: str
    is_user: bool
    timestamp: str
    battle_log: Optional[Dict] = None

class ChatHistory:
    def __init__(self):
        self.messages: List[ChatMessage] = []
        self.initial_message = ChatMessage(
            content="Hello! I'm your battle partner. You can chat with me about strategy or challenge me to a battle!",
            is_user=False,
            timestamp=datetime.now().isoformat()
        )
        self.messages.append(self.initial_message)
        self.current_battle = None
        self.current_battle_message_index = None 

    def add_message(self, content: str, is_user: bool):
        message = ChatMessage(
            content=content,
            is_user=is_user,
            timestamp=datetime.now().isoformat()
        )
        self.messages.append(message)

    def start_battle(self, battle_id: str):
        """Initialize a new battle in the chat history"""
        self.current_battle = {'id': battle_id, 'turns': []}
        self.current_battle_message_index = len(self.messages) - 1
        if self.current_battle_message_index >= 0:
            # Add battle log to the last message (which should be the battle start message)
            self.messages[self.current_battle_message_index].battle_log = self.current_battle

    def add_battle_turn(self, battle_id: str, turn_data: Dict, message: str):
        """Add a battle turn update and append it to the current battle message"""
        if not self.current_battle or battle_id != self.current_battle['id']:
            return
            
        # Create a cleaner turn entry
        turn_entry = {
            'number': len(self.current_battle['turns']) + 1,
            'description': message.strip()  # Strip any extra whitespace
        }
        
        # Add the turn
        self.current_battle['turns'].append(turn_entry)
        
        # Update the message
        if self.current_battle_message_index is not None:
            # Get the current content
            current_content = self.messages[self.current_battle_message_index].content
            
            # If this is the first turn, make sure we have the battle header
            if len(self.current_battle['turns']) == 1 and "Battle Started" not in current_content:
                current_content = "Battle Started\n" + current_content
            
            # Add the new turn
            self.messages[self.current_battle_message_index].content = (
                f"{current_content}\n\n"
                f"Turn {turn_entry['number']}:\n"
                f"{turn_entry['description']}"
            )
            
            # Update the battle log
            self.messages[self.current_battle_message_index].battle_log = self.current_battle

    def end_battle(self, battle_id: str, conclusion: str):
        """End the battle and add a conclusion message"""
        if not self.current_battle or battle_id != self.current_battle['id']:
            return
            
        self.current_battle['is_complete'] = True
        self.current_battle['conclusion'] = conclusion
        self.messages[self.current_battle_message_index].battle_log = self.current_battle
        self.messages[self.current_battle_message_index].content += f"\n\n{conclusion}"
        
        self.current_battle = None
        self.current_battle_message_index = None

    def get_messages(self):
        return [asdict(msg) for msg in self.messages]

def run_coroutine_threadsafe(coro):
    """Safely run a coroutine in the background loop"""
    global background_loop
    if background_loop and not background_loop.is_closed():
        future = asyncio.run_coroutine_threadsafe(coro, background_loop)
        return future

def background_thread():
    """Background thread to run the asyncio event loop"""
    global background_loop
    background_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(background_loop)
    background_loop.run_forever()

def initialize_system():
    global system, background_loop
    
    if system is None:
        username = os.getenv('PS_USERNAME', 'default_username')
        password = os.getenv('PS_PASSWORD', 'default_password')
        system = SystemManager(username, password)
        system.chat_history = ChatHistory()
        
        # Start background thread for async operations if not already running
        if background_loop is None or background_loop.is_closed():
            thread = threading.Thread(target=background_thread, daemon=True)
            thread.start()
    
    return system

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/get_chat_history')
def get_chat_history():
    if not system:
        initialize_system()
    return jsonify({'messages': system.chat_history.get_messages()})

@app.route('/get_battle_updates')
def get_battle_updates():
    """Endpoint to get current battle status and updates"""
    if not system or not system.chat_history.current_battle:
        return jsonify({'has_updates': False})
    return jsonify({
        'has_updates': True,
        'battle': system.chat_history.current_battle
    })

@app.route('/forfeit_battle')
def forfeit_battle():
    """Endpoint to handle battle forfeits"""
    if not system or not system.chat_history.current_battle:
        return jsonify({'error': 'No active battle'}), 400
        
    try:
        battle_id = system.chat_history.current_battle['id']
        system.chat_history.end_battle(battle_id, "Battle forfeited by user.")
        # TODO: Add actual battle forfeit logic in system_manager
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/send_message', methods=['POST'])
def send_message():
    if not system:
        initialize_system()
        
    message = request.json.get('message')
    if not message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        # Add user message to history
        system.chat_history.add_message(message, is_user=True)

        # Get response from the agent
        response = system.agent.run(message)
        conversation, tool = system.agent.extract_tool_call(response)

        # Handle battle requests
        battle_started = False
        if tool == "BATTLE_MANAGER":
            try:
                battle_id = datetime.now().strftime("%Y%m%d%H%M%S")
                print(f"\nStarting battle with ID: {battle_id}")
                
                # Initialize battle state in chat history before starting battle
                system.chat_history.start_battle(battle_id)
                
                # Start battle and get future
                future = run_coroutine_threadsafe(system.start_battle("rightnow3day"))
                
                # Add callback to handle battle start result
                def handle_battle_result(fut):
                    try:
                        fut.result()  # This will raise any exceptions that occurred
                        print(f"Battle {battle_id} started successfully")
                    except Exception as e:
                        print(f"Battle failed to start: {str(e)}")
                        system.chat_history.end_battle(battle_id, f"Failed to start battle: {str(e)}")
                
                future.add_done_callback(handle_battle_result)
                battle_started = True
                
            except Exception as e:
                print(f"Error in battle setup: {str(e)}", exc_info=True)
                raise RuntimeError(f"Failed to setup battle: {str(e)}")

        # Add assistant's response to history
        system.chat_history.add_message(conversation, is_user=False)

        return jsonify({
            'response': conversation,  # Using original agent response
            'messages': system.chat_history.get_messages(),
            'battle_started': battle_started
        })

    except Exception as e:
        print(f"Error in send_message: {str(e)}", exc_info=True)
        error_msg = f"An error occurred: {str(e)}"
        if system and hasattr(system, 'chat_history'):
            system.chat_history.add_message(error_msg, is_user=False)
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    initialize_system()
    app.run(debug=True)