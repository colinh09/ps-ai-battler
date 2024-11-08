from typing import Dict, List, Optional
import asyncio
from ps_bot.ps_client import ShowdownBot
from agents.agent import PSAgent

class BattleManager:
    """
    Manages the interaction between the Pokemon Showdown client (ShowdownBot) 
    and the AI agent.
    """
    def __init__(self, username: str, password: str, target_username: str, db_params: Dict[str, str]):
        """
        Initialize the battle manager with credentials and database connection.
        
        Args:
            username (str): Pokemon Showdown username
            password (str): Pokemon Showdown password
            target_username (str): Username of the player to challenge
            db_params (dict): Database connection parameters
        """
        self.bot = ShowdownBot(username, password, target_username)
        self.agent = PSAgent(db_params=db_params)
        self.current_state = None
        self.is_running = False

    def get_pokemon_context(self, state: Dict) -> str:
        """
        Get detailed information about the active Pokemon from the database.
        
        Args:
            state (Dict): Current battle state
            
        Returns:
            str: Formatted context about both active Pokemon
        """
        context_parts = []
        
        # Get active Pokemon names
        self_pokemon = state["active"]["self"]["name"] if state["active"]["self"] else None
        opponent_pokemon = state["active"]["opponent"]["name"] if state["active"]["opponent"] else None
        
        # Get database information for both Pokemon
        if self_pokemon:
            self_data = self.agent.db_tools.get_pokemon_complete_data(self_pokemon)
            if "error" not in self_data:
                context_parts.append("YOUR ACTIVE POKEMON INFORMATION:")
                context_parts.append(self.agent.format_pokemon_data(self_data))
        
        if opponent_pokemon:
            opponent_data = self.agent.db_tools.get_pokemon_complete_data(opponent_pokemon)
            if "error" not in opponent_data:
                context_parts.append("\nOPPONENT'S ACTIVE POKEMON INFORMATION:")
                context_parts.append(self.agent.format_pokemon_data(opponent_data))
        
        return "\n".join(context_parts)

    def parse_battle_state(self, state: Dict) -> str:
        """
        Parse the battle state into a formatted string for the agent.
        
        Args:
            state (Dict): Current battle state dictionary
            
        Returns:
            str: Formatted battle state description
        """
        if not state:
            return "No active battle state."
            
        output = []
        
        # Get Pokemon database context first
        pokemon_context = self.get_pokemon_context(state)
        if pokemon_context:
            output.append(pokemon_context)
            output.append("\n=== CURRENT BATTLE SITUATION ===\n")
        else:
            output.append("=== CURRENT BATTLE SITUATION ===\n")
        
        # Active Pokemon Section
        output.append("YOUR ACTIVE POKEMON:")
        if state["active"]["self"]:
            pokemon = state["active"]["self"]
            hp_val, max_hp = pokemon["hp"].split('/')
            hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
            
            output.append(f"- {pokemon['name']} (HP: {hp_percent}%)")
            if pokemon["status"]:
                output.append(f"  Status: {pokemon['status']}")
            if pokemon["ability"]:
                output.append(f"  Ability: {pokemon['ability']}")
            if pokemon["moves"]:
                output.append(f"  Known moves: {', '.join(pokemon['moves'])}")
            boosts = [f"{stat.upper()}: {val:+d}" for stat, val in pokemon["boosts"].items() if val != 0]
            if boosts:
                output.append(f"  Boosts: {', '.join(boosts)}")
        
        output.append("\nOPPONENT'S ACTIVE POKEMON:")
        if state["active"]["opponent"]:
            pokemon = state["active"]["opponent"]
            hp_val, max_hp = pokemon["hp"].split('/')
            hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
            
            output.append(f"- {pokemon['name']} (HP: {hp_percent}%)")
            if pokemon["status"]:
                output.append(f"  Status: {pokemon['status']}")
            if pokemon["ability"]:
                output.append(f"  Ability: {pokemon['ability']}")
            if pokemon["moves"]:
                output.append(f"  Known moves: {', '.join(pokemon['moves'])}")
            boosts = [f"{stat.upper()}: {val:+d}" for stat, val in pokemon["boosts"].items() if val != 0]
            if boosts:
                output.append(f"  Boosts: {', '.join(boosts)}")
        
        # Team Section
        output.append("\nYOUR TEAM:")
        for name, pokemon in state["team"]["self"].items():
            hp_val, max_hp = pokemon["hp"].split('/')
            hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
            status_str = f", Status: {pokemon['status']}" if pokemon["status"] else ""
            ability_str = f", Ability: {pokemon['ability']}" if pokemon["ability"] else ""
            output.append(f"- {name} (HP: {hp_percent}%{status_str}{ability_str})")
            if pokemon["moves"]:
                output.append(f"  Known moves: {', '.join(pokemon['moves'])}")
        
        output.append("\nREVEALED OPPONENT POKEMON:")
        for name, pokemon in state["team"]["opponent"].items():
            hp_val, max_hp = pokemon["hp"].split('/')
            hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
            status_str = f", Status: {pokemon['status']}" if pokemon["status"] else ""
            ability_str = f", Ability: {pokemon['ability']}" if pokemon["ability"] else ""
            output.append(f"- {name} (HP: {hp_percent}%{status_str}{ability_str})")
            if pokemon["moves"]:
                output.append(f"  Known moves: {', '.join(pokemon['moves'])}")
        
        # Field Conditions
        output.append("\nFIELD CONDITIONS:")
        conditions = []
        if state["field_conditions"]["weather"]:
            conditions.append(f"Weather: {state['field_conditions']['weather']}")
        if state["field_conditions"]["terrain"]:
            conditions.append(f"Terrain: {state['field_conditions']['terrain']}")
        if state["field_conditions"]["trick_room"]:
            conditions.append("Trick Room is active")
        if not conditions:
            conditions.append("No active field conditions")
        output.extend([f"- {condition}" for condition in conditions])
        
        # Side Conditions
        output.append("\nSIDE CONDITIONS:")
        output.append("Your side:")
        if state["side_conditions"]["self"]["hazards"]:
            output.append(f"- Hazards: {', '.join(state['side_conditions']['self']['hazards'])}")
        if state["side_conditions"]["self"]["screens"]:
            output.append(f"- Screens: {', '.join(state['side_conditions']['self']['screens'])}")
            
        output.append("Opponent's side:")
        if state["side_conditions"]["opponent"]["hazards"]:
            output.append(f"- Hazards: {', '.join(state['side_conditions']['opponent']['hazards'])}")
        if state["side_conditions"]["opponent"]["screens"]:
            output.append(f"- Screens: {', '.join(state['side_conditions']['opponent']['screens'])}")
        
        # Available Actions
        if state["waiting_for_decision"]:
            output.append("\nAVAILABLE ACTIONS:")
            if state["valid_moves"]:
                output.append("Available moves:")
                for move in state["valid_moves"]:
                    output.append(f"- Move {move['index']}: {move['move']} (PP: {move['pp']}/{move['maxpp']})")
            
            if state["valid_switches"]:
                output.append("\nAvailable switches:")
                for switch in state["valid_switches"]:
                    output.append(f"- Switch {switch['index']}: {switch['pokemon']} ({switch['condition']})")
        
        output.append("\n=== END BATTLE SITUATION ===")
        
        return "\n".join(output)

    async def start(self):
        """Start the battle manager and establish connection to Pokemon Showdown"""
        self.is_running = True
        await self.bot.connect()
        await self.run_battle_loop()

    def get_current_state(self) -> Optional[Dict]:
        """Get the current battle state from the ShowdownBot"""
        return self.bot.get_game_state() if self.bot.current_battle else None

    async def make_move(self, move_instruction: str) -> Dict:
        """
        Execute a move through the ShowdownBot.
        
        Args:
            move_instruction (str): Move instruction in format "move X" or "switch X"
            
        Returns:
            Dict: Result of the move attempt with success status and any error message
        """
        return await self.bot.handle_instruction(move_instruction)

    async def get_agent_decision(self, state: Dict) -> tuple[str, Optional[str]]:
        """
        Get the agent's decision based on the current battle state.
        
        Args:
            state (Dict): Current battle state
            
        Returns:
            tuple[str, Optional[str]]: (reasoning, move_command) where move_command is in format 'move X' or 'switch X'
        """
        # Format the battle state with Pokemon context
        formatted_state = self.parse_battle_state(state)
        
        # Create the query for the agent with explicit formatting instructions
        query = f"""Based on the following battle situation, what would be the best move to make? Consider all available moves and switches.

    {formatted_state}

    Analyze the situation and explain your reasoning. Then, provide your chosen move in a separate line starting with "CHOSEN MOVE:".
    For example:
    - If choosing a move, write "CHOSEN MOVE: move X" (e.g., "CHOSEN MOVE: move 1")
    - If choosing to switch, write "CHOSEN MOVE: switch X" (e.g., "CHOSEN MOVE: switch 3")

    Make sure to separate your analysis from your move choice with a blank line."""

        # Get the agent's response
        response = self.agent.run(query)
        
        # Parse the response to separate reasoning from move command
        try:
            # Split on "CHOSEN MOVE:" and handle potential formatting issues
            parts = response.split("CHOSEN MOVE:")
            
            if len(parts) != 2:
                print("Warning: Agent response not properly formatted. Showing analysis only.")
                return response, None
                
            reasoning = parts[0].strip()
            move_command = parts[1].strip()
            
            # Validate move command format
            if not (move_command.startswith("move ") or move_command.startswith("switch ")):
                print(f"Warning: Invalid move command format: {move_command}")
                return reasoning, None
                
            print("\nAgent's analysis:")
            print(reasoning)
            print(f"\nChosen move: {move_command}")
            
            return reasoning, move_command
            
        except Exception as e:
            print(f"Error parsing agent response: {str(e)}")
            print("Raw response:", response)
            return response, None

    async def run_battle_loop(self):
        """Main loop that monitors the battle state and handles moves"""
        try:
            while self.is_running:
                receive_task = asyncio.create_task(self.bot.receive_messages())
                
                last_state_hash = None  # Use this to track actual state changes
                
                while self.is_running:
                    new_state = self.get_current_state()
                    
                    # Create a simple hash of relevant state parts to detect actual changes
                    if new_state:
                        current_hash = (
                            str(new_state.get('active')),
                            str(new_state.get('field_conditions')),
                            str(new_state.get('side_conditions')),
                            new_state.get('waiting_for_decision'),
                            str(new_state.get('valid_moves')),
                            str(new_state.get('valid_switches'))
                        )
                    else:
                        current_hash = None
                    
                    # Only update and print if there's an actual state change
                    if current_hash != last_state_hash:
                        self.current_state = new_state
                        last_state_hash = current_hash
                        
                        if new_state and new_state["waiting_for_decision"]:
                            formatted_state = self.parse_battle_state(new_state)
                            print("\n" + formatted_state)
                            
                            # Get agent's analysis and move choice
                            reasoning, move_command = await self.get_agent_decision(new_state)
                            
                            if move_command:
                                # Execute the move
                                result = await self.make_move(move_command)
                                if not result["success"]:
                                    print(f"Move execution failed: {result['error']}")
                        
                    await asyncio.sleep(0.5)  # Increased sleep time to reduce polling
                
                receive_task.cancel()
            
        except Exception as e:
            print(f"Error in battle loop: {str(e)}")
            self.is_running = False

async def main():
    """Example usage of the BattleManager"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    USERNAME = os.getenv('PS_USERNAME')
    PASSWORD = os.getenv('PS_PASSWORD')
    TARGET_USERNAME = os.getenv('PS_TARGET_USERNAME', 'blueudon')
    
    # Database connection parameters
    db_params = {
        'dbname': 'pokemon',
        'user': 'postgres',
        'password': 'password',
        'host': 'localhost',
        'port': '5432'
    }
    
    if not USERNAME or not PASSWORD:
        print("Error: Please set PS_USERNAME and PS_PASSWORD environment variables")
        return
    
    manager = BattleManager(USERNAME, PASSWORD, TARGET_USERNAME, db_params)
    
    try:
        await manager.start()
    except KeyboardInterrupt:
        print("\nBattle manager stopped by user")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())