import streamlit as st
import asyncio
from battle_manager import BattleManager
from agents.converse_agent import PokemonTrainerAgent
from ps_bot.ps_client import ShowdownBot
import logging
from typing import Optional, List
import nest_asyncio
from pokemon_db_tools import PokemonDBTools

# Enable nested asyncio for Streamlit
nest_asyncio.apply()

# Initialize session state
if 'battle_running' not in st.session_state:
    st.session_state.battle_running = False
if 'bot' not in st.session_state:
    st.session_state.bot = None
if 'battle_manager' not in st.session_state:
    st.session_state.battle_manager = None
if 'agent' not in st.session_state:
    st.session_state.agent = None
if 'event_loop' not in st.session_state:
    st.session_state.event_loop = None
if 'db_tools' not in st.session_state:
    st.session_state.db_tools = None

def get_db_params() -> dict:
    """Get database connection parameters"""
    return {
        'dbname': 'pokemon',
        'user': 'postgres',
        'password': 'password',
        'host': 'localhost',
        'port': '5432'
    }

def format_personality(personality: str) -> str:
    """Format personality string for internal use"""
    if personality in ["arrogant rival", "supportive rival"]:
        return personality.replace(" ", "_")
    return personality

async def lookup_pokemon(pokemon_names: List[str], sender: str, original_query: str):
    """Look up Pokemon information and send informed response"""
    try:
        # Initialize DB tools if not already done
        if not st.session_state.db_tools:
            st.session_state.db_tools = PokemonDBTools(get_db_params())
        
        # Look up Pokemon data
        pokemon_data = st.session_state.db_tools.batch_pokemon_lookup(
            pokemon_names,
            include_randbats=False
        )
        
        # Have agent formulate informed response
        response = st.session_state.agent.run(
            f"""The user's original question was: {original_query}

            Here is the detailed data for the Pokemon mentioned:
            {pokemon_data}
            
            Please provide an informed response that answers their question,
            incorporating these specific details about the Pokemon."""
        )
        
        # Send informed response
        if response:
            await st.session_state.bot.send_pm(sender, response)
            
    except Exception as e:
        st.error(f"Error looking up Pokemon: {str(e)}")
        await st.session_state.bot.send_pm(
            sender, 
            "I apologize, but I encountered an error looking up that Pokemon information."
        )

async def handle_message(message: str, username: str, password: str, target_username: str, personality: str):
    """Handle incoming messages from Pokemon Showdown"""
    if "|pm|" in message:
        parts = message.split("|")
        if len(parts) >= 5:
            sender = parts[2].strip()
            content = parts[4]
            
            if (sender.lower().strip() == target_username.lower().strip() and 
                "rejected the challenge" not in content and 
                "accepted the challenge" not in content and 
                content != "/challenge"):
                
                # Get agent's response
                response = st.session_state.agent.run(content)
                conversation, tool = st.session_state.agent.extract_tool_call(response)
                
                # Always send the conversation response first
                if conversation:
                    await st.session_state.bot.send_pm(sender, conversation)
                
                # Then handle any tool calls
                if tool:
                    if tool == "BATTLE_MANAGER":
                        await start_battle(username, password, sender, personality)
                    elif tool.startswith("POKEMON_SEARCH"):
                        pokemon_names = tool.replace("POKEMON_SEARCH", "").strip().split(",")
                        await lookup_pokemon(pokemon_names, sender, content)
                else:
                    # No tool call, just send conversation response
                    if conversation:
                        await st.session_state.bot.send_pm(sender, conversation)
    
    elif "|challstr|" in message:
        challstr = message.split("|challstr|")[1]
        await st.session_state.bot.login(challstr, True)

async def start_pokemon_system(username: str, password: str, target_username: str, personality: str):
    """Start the Pokemon battle system"""
    try:
        formatted_personality = format_personality(personality)
        
        # Initialize bot and agent
        st.session_state.bot = ShowdownBot(username, password, target_username)
        st.session_state.agent = PokemonTrainerAgent(personality=formatted_personality)
        
        # Connect to Pokemon Showdown
        await st.session_state.bot.connect()
        st.success("Connected to Pokemon Showdown!")
        
        while st.session_state.battle_running:
            try:
                message = await st.session_state.bot.ws.recv()
                await handle_message(message, username, password, target_username, formatted_personality)
                    
            except Exception as e:
                continue
                
    except Exception as e:
        reset_system()

async def start_battle(username: str, password: str, opponent_username: str, personality: str):
    """Start a battle with the specified opponent"""
    try:
        st.info(f"Starting battle with {opponent_username}")
        
        # Create new battle manager
        st.session_state.battle_manager = BattleManager(
            username=username,
            password=password,
            target_username=opponent_username,
            db_params=get_db_params(),
            personality=personality
        )
        
        # Connect battle manager's bot
        await st.session_state.battle_manager.bot.connect()
        st.success("Battle connection established!")
        
        # Initialize battle loop
        st.session_state.battle_manager.is_running = True
        st.session_state.battle_manager.battle_concluded = False
        
        # Use current event loop instead of creating a new one
        receive_task = asyncio.create_task(st.session_state.battle_manager.bot.receive_messages())
        battle_task = asyncio.create_task(st.session_state.battle_manager.run_battle_loop())
        
        # Wait for battle to complete
        await asyncio.gather(receive_task, battle_task)
        
        # Generate battle analysis
        await send_battle_analysis(opponent_username)
        
    except Exception as e:
        if st.session_state.battle_manager:
            st.session_state.battle_manager.is_running = False

async def send_battle_analysis(opponent_username: str):
    """Generate and send battle analysis"""
    if st.session_state.battle_manager:
        await st.session_state.battle_manager.bot.send_pm(
            opponent_username, 
            "Analyzing battle results..."
        )
        
        final_state = st.session_state.battle_manager.current_state
        battle_history = st.session_state.battle_manager.bot.get_battle_history_text()
        
        if final_state and battle_history:
            analysis = st.session_state.battle_manager.agent.run(
                f"""Analyze this completed Pokemon battle. Review the battle history and final state to provide insights.

                Battle History:
                {battle_history}

                Final Battle State:
                {st.session_state.battle_manager.parse_battle_state(final_state)}

                Please provide:
                1. An overview of how the battle progressed
                2. Key turning points or critical moments
                3. Effective strategies that were used
                4. Areas for improvement
                5. Notable matchups and how they influenced the battle
                
                Focus on constructive analysis that could help improve future battles. Use paragraphs with no headers."""
            )
            
            if analysis:
                await st.session_state.battle_manager.bot.send_pm(opponent_username, analysis)

def reset_system():
    """Reset the Pokemon battle system"""
    st.session_state.battle_running = False
    st.session_state.bot = None
    st.session_state.battle_manager = None
    st.session_state.agent = None
    st.session_state.db_tools = None
    
    if st.session_state.event_loop:
        try:
            st.session_state.event_loop.stop()
            st.session_state.event_loop.close()
        except:
            pass
        st.session_state.event_loop = None
    
    st.success("System reset successfully!")

def main():
    st.title("Pokemon Battle Bot")
    st.write("Configure and control your Pokemon battle bot")
    
    # Configuration section
    st.header("Configuration")
    
    # API Key input with default from secrets
    api_key = st.text_input(
        "Samba Nova API Key", 
        value=st.secrets.get('SAMBA_NOVA_API_KEY', ''),
        type="password"
    )
    
    # Pokemon Showdown credentials with defaults from secrets
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input(
            "Pokemon Showdown Username",
            value=st.secrets.get('PS_USERNAME', '')
        )
    with col2:
        password = st.text_input(
            "Pokemon Showdown Password",
            value=st.secrets.get('PS_PASSWORD', ''),
            type="password"
        )
    
    # Target username with default from secrets
    target_username = st.text_input(
        "Target Username",
        value=st.secrets.get('PS_TARGET_USERNAME', '')
    )
    
    # Personality selector with display names and default from secrets
    personality_options = {
        "arrogant rival": "Arrogant Rival",
        "supportive rival": "Supportive Rival",
        "professor": "Professor",
        "npc": "NPC"
    }
    default_personality = st.secrets.get('DEFAULT_PERSONALITY', 'professor')
    default_index = list(personality_options.keys()).index(default_personality) if default_personality in personality_options else 0
    
    personality = st.selectbox(
        "Select Personality",
        list(personality_options.keys()),
        index=default_index,
        format_func=lambda x: personality_options[x]
    )
    
    # Single button that changes from Start to Reset Session
    if st.button("Start" if not st.session_state.battle_running else "Reset Session"):
        if not st.session_state.battle_running:
            # Validate inputs
            if not all([api_key, username, password, target_username]):
                st.error("Please fill in all required fields!")
                return
            
            # Start the system
            st.session_state.battle_running = True
            asyncio.run(start_pokemon_system(username, password, target_username, personality))
        else:
            # Reset the system
            reset_system()
    
    # Status indicator
    if st.session_state.battle_running:
        st.success("System is running")
    else:
        st.warning("System is stopped")

if __name__ == "__main__":
    main()