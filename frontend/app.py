# frontend/app.py
from flask import Flask, render_template, request, jsonify
import sys
import os

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from system_manager import SystemManager

app = Flask(__name__)

# Initialize SystemManager
system = None

def initialize_system():
    global system
    username = os.getenv('PS_USERNAME', 'default_username')
    password = os.getenv('PS_PASSWORD', 'default_password')
    system = SystemManager(username, password)
    return system

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    if not system:
        initialize_system()
        
    message = request.json.get('message')
    if not message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        # Get response from the agent
        response = system.agent.run(message)
        conversation, tool = system.agent.extract_tool_call(response)

        # Handle battle requests
        if tool == "BATTLE_MANAGER":
            conversation += "\n(Battle request received!)"

        return jsonify({
            'response': conversation
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    initialize_system()
    app.run(debug=True)