from typing import Dict, List, Optional
import asyncio
from ps_bot.ps_client import ShowdownBot
from agents.agent import PSAgent
from datetime import datetime
import logging
"""
Pokemon Showdown Battle Bot System
================================

This system consists of three main components working together to play Pokemon Showdown battles:

1. ShowdownBot (ps_client.py):
   - Handles direct communication with Pokemon Showdown servers
   - Manages battle state, moves, and Pokemon data
   - Executes commands in the actual battle

2. BattleManager (battle_manager.py):
   - Coordinates between ShowdownBot and AI agent
   - Formats battle data for AI consumption
   - Manages the battle loop and decision execution

3. PSAgent (ps_agent.py):
   - Makes battle decisions using LLM (AI)
   - Accesses Pokemon database for detailed information
   - Provides strategic analysis and move choices

Basic Flow:
-----------
1. System connects to Pokemon Showdown
2. Bot receives battle state updates
3. Manager formats battle state for AI
4. AI analyzes situation and chooses move
5. Manager sends agent response (move to make + reasoning) to the bot
6. Bot executes move in battle
7. Wait for next game state and repeat from step 1

The system runs asynchronously, continuously monitoring the battle state
and making decisions when required.
"""


class BattleManager:
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
        self.logger = logging.getLogger('BattleManager')
        self.initial_connection_made = False
        self.battle_concluded = False
        
        self.bot.on_battle_end = self.handle_battle_end

    def handle_battle_end(self):
        """Handler for battle end events"""
        self.logger.info("Battle has concluded")
        self.battle_concluded = True
        self.is_running = False

    async def forfeit(self) -> bool:
        """Forfeit the current battle"""
        try:
            if not self.bot or not self.is_running:
                return False
                
            success = await self.bot.forfeit_battle()
            if success:
                self.is_running = False
                self.battle_concluded = True
                if self.on_battle_end:
                    self.on_battle_end()
            return success
        except Exception as e:
            self.logger.error(f"Error in forfeit: {str(e)}")
            return False


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
            # Prepare known data for agent's Pokemon
            known_data = {}
            if state["active"]["self"].get("ability"):
                known_data["ability"] = state["active"]["self"]["ability"]
            if state["active"]["self"].get("item"):
                known_data["item"] = state["active"]["self"]["item"]
            if state["active"]["self"].get("moves"):
                known_data["moves"] = state["active"]["self"]["moves"]
            
            self_data = self.agent.db_tools.get_pokemon_complete_data(self_pokemon, known_data)
            if "error" not in self_data:
                context_parts.append("YOUR ACTIVE POKEMON INFORMATION:")
                context_parts.append(self.agent.format_pokemon_data(self_data))
        
        if opponent_pokemon:
            # For opponent Pokemon, we don't pass known_data so it merges all possible sets
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
        output.append("=== CURRENT BATTLE SITUATION ===\n")
        
        # Get Pokemon database context for both active Pokemon
        self_pokemon = state["active"]["self"]["name"] if state["active"]["self"] else None
        opponent_pokemon = state["active"]["opponent"]["name"] if state["active"]["opponent"] else None
        
        if self_pokemon:
            # Get known data for our Pokemon
            known_data = {}
            if state["active"]["self"].get("ability"):
                known_data["ability"] = state["active"]["self"]["ability"]
            if state["active"]["self"].get("item"):
                known_data["item"] = state["active"]["self"]["item"]
            if state["active"]["self"].get("moves"):
                known_data["moves"] = state["active"]["self"]["moves"]
                
            # Get complete Pokemon data including type matchups
            pokemon_data = self.agent.db_tools.get_pokemon_complete_data(self_pokemon, known_data)
            
            output.append("YOUR ACTIVE POKEMON:")
            pokemon = state["active"]["self"]
            
            # Handle fainted Pokemon case
            if pokemon["hp"] == "0" or pokemon["hp"] == "0 fnt" or "fnt" in pokemon["hp"]:
                hp_percent = 0
            else:
                try:
                    hp_val, max_hp = pokemon["hp"].split('/')
                    hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                except (ValueError, IndexError):
                    hp_percent = 0
                    print(f"Warning: Could not parse HP value: {pokemon['hp']}")
            
            output.append(f"- {pokemon['name']} (HP: {hp_percent}%)")
            
            # Add Role from random battle data
            if 'random_battle_data' in pokemon_data and pokemon_data['random_battle_data'].get('roles'):
                output.append(f"  Role: {', '.join(pokemon_data['random_battle_data']['roles'])}")
                
            # Add type matchups
            if 'type_matchups' in pokemon_data:
                output.append("  Type Matchups:")
                weaknesses = [f"{t} ({m}x)" for t, m in pokemon_data['type_matchups']['defending'].items() if m > 1]
                resistances = [f"{t} ({m}x)" for t, m in pokemon_data['type_matchups']['defending'].items() if m < 1 and m > 0]
                immunities = [t for t, m in pokemon_data['type_matchups']['defending'].items() if m == 0]
                
                if weaknesses:
                    output.append(f"    Weak to: {', '.join(weaknesses)}")
                if resistances:
                    output.append(f"    Resists: {', '.join(resistances)}")
                if immunities:
                    output.append(f"    Immune to: {', '.join(immunities)}")
            
            # Add ability info
            if pokemon["ability"]:
                ability_data = self.agent.db_tools.get_ability_data(pokemon["ability"])
                if ability_data:
                    output.append(f"  Ability: {ability_data['ability_name']}")
                    output.append(f"    Description: {ability_data['description']}")
            
            # Add moves with details
            if pokemon["moves"]:
                output.append("  Known moves:")
                for move_name in pokemon["moves"]:
                    move_data = self.agent.db_tools.get_move_data(move_name)
                    if move_data:
                        output.append(f"    - {move_data['move_name']} (Type: {move_data['type']}, "
                                    f"Power: {move_data['power']}, Accuracy: {move_data['accuracy']})")
                        output.append(f"      Description: {move_data['description']}")
            
            # Add item info
            if pokemon.get("item"):
                item_data = self.agent.db_tools.get_item_data(pokemon["item"])
                if item_data:
                    output.append(f"  Item: {item_data['item_name']}")
                    output.append(f"    Description: {item_data['description']}")
            
            # Add Tera Type info
            if pokemon.get("tera_type"):
                output.append(f"  Tera Type: {pokemon['tera_type']}")
                if pokemon.get("terastallized"):
                    output.append("  Currently Terastallized")
                elif not state.get("tera_used", False):
                    output.append("  Can Terastallize")
            
            # Add volatile status
            if pokemon.get("volatile_status"):
                output.append(f"  Volatile Status: {', '.join(pokemon['volatile_status'])}")
            
            # Add stat boosts
            if pokemon["boosts"]:
                boosts = [f"{stat.upper()}: {val:+d}" for stat, val in pokemon["boosts"].items() if val != 0]
                if boosts:
                    output.append(f"  Boosts: {', '.join(boosts)}")
            
            # Add stats
            if pokemon.get("stats"):
                stats = [f"{stat.upper()}: {val}" for stat, val in pokemon["stats"].items() if val != 0]
                if stats:
                    output.append(f"  Stats: {', '.join(stats)}")
        
        if opponent_pokemon:
            # Get opponent Pokemon data
            opponent_data = self.agent.db_tools.get_pokemon_complete_data(opponent_pokemon)
            random_battle_data = opponent_data.get('random_battle_data', {})
            
            output.append("\nOPPONENT'S ACTIVE POKEMON:")
            pokemon = state["active"]["opponent"]
            
            # Handle fainted Pokemon case
            if pokemon["hp"] == "0" or pokemon["hp"] == "0 fnt" or "fnt" in pokemon["hp"]:
                hp_percent = 0
            else:
                try:
                    hp_val, max_hp = pokemon["hp"].split('/')
                    hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                except (ValueError, IndexError):
                    hp_percent = 0
                    print(f"Warning: Could not parse HP value: {pokemon['hp']}")
            
            output.append(f"- {pokemon['name']} (HP: {hp_percent}%)")
            
            # Add type matchups
            if 'type_matchups' in opponent_data:
                output.append("  Type Matchups:")
                weaknesses = [f"{t} ({m}x)" for t, m in opponent_data['type_matchups']['defending'].items() if m > 1]
                resistances = [f"{t} ({m}x)" for t, m in opponent_data['type_matchups']['defending'].items() if m < 1 and m > 0]
                immunities = [t for t, m in opponent_data['type_matchups']['defending'].items() if m == 0]
                
                if weaknesses:
                    output.append(f"    Weak to: {', '.join(weaknesses)}")
                if resistances:
                    output.append(f"    Resists: {', '.join(resistances)}")
                if immunities:
                    output.append(f"    Immune to: {', '.join(immunities)}")
            
            # Add all possibilities from random battle data
            if random_battle_data.get('roles'):
                output.append(f"  Possible Roles: {', '.join(random_battle_data['roles'])}")
            if random_battle_data.get('level'):
                output.append(f"  Level: {random_battle_data['level']}")
            if random_battle_data.get('abilities'):
                output.append(f"  Possible Abilities: {', '.join(random_battle_data['abilities'])}")
            if random_battle_data.get('items'):
                output.append(f"  Possible Items: {', '.join(random_battle_data['items'])}")
            if random_battle_data.get('moves'):
                output.append(f"  Possible Moves: {', '.join(random_battle_data['moves'])}")
            if random_battle_data.get('tera_types'):
                output.append(f"  Possible Tera Types: {', '.join(random_battle_data['tera_types'])}")
            
            # Add known information
            if pokemon["status"]:
                output.append(f"  Status: {pokemon['status']}")
            if pokemon["ability"]:
                ability_data = self.agent.db_tools.get_ability_data(pokemon["ability"])
                if ability_data:
                    output.append(f"  Known Ability: {ability_data['ability_name']}")
                    output.append(f"    Description: {ability_data['description']}")
            
            # Add known moves with details
            if pokemon["moves"]:
                output.append("  Revealed Moves:")
                for move_name in pokemon["moves"]:
                    move_data = self.agent.db_tools.get_move_data(move_name)
                    if move_data:
                        output.append(f"    - {move_data['move_name']} (Type: {move_data['type']}, "
                                    f"Power: {move_data['power']}, Accuracy: {move_data['accuracy']})")
                        output.append(f"      Description: {move_data['description']}")
            
            if pokemon.get("item"):
                item_data = self.agent.db_tools.get_item_data(pokemon["item"])
                if item_data:
                    output.append(f"  Known Item: {item_data['item_name']}")
                    output.append(f"    Description: {item_data['description']}")
            
            if pokemon.get("tera_type"):
                output.append(f"  Known Tera Type: {pokemon['tera_type']}")
                if pokemon.get("terastallized"):
                    output.append("  Currently Terastallized")
            
            if pokemon.get("volatile_status"):
                output.append(f"  Volatile Status: {', '.join(pokemon['volatile_status'])}")
            
            if pokemon["boosts"]:
                boosts = [f"{stat.upper()}: {val:+d}" for stat, val in pokemon["boosts"].items() if val != 0]
                if boosts:
                    output.append(f"  Boosts: {', '.join(boosts)}")
            
            if pokemon.get("stats"):
                stats = [f"{stat.upper()}: {val}" for stat, val in pokemon["stats"].items() if val != 0]
                if stats:
                    output.append(f"  Stats: {', '.join(stats)}")
        
        # Team Section
        output.append("\nYOUR TEAM:")
        for name, pokemon in state["team"]["self"].items():
            # Get complete data for team member
            pokemon_data = self.agent.db_tools.get_pokemon_complete_data(name)
            
            # Handle fainted Pokemon case
            if pokemon["hp"] == "0" or pokemon["hp"] == "0 fnt" or "fnt" in pokemon["hp"]:
                hp_percent = 0
            else:
                try:
                    hp_val, max_hp = pokemon["hp"].split('/')
                    hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                except (ValueError, IndexError):
                    hp_percent = 0
                    print(f"Warning: Could not parse HP value: {pokemon['hp']}")
            
            status_str = f", Status: {pokemon['status']}" if pokemon["status"] else ""
            ability_str = ""
            if pokemon["ability"]:
                ability_data = self.agent.db_tools.get_ability_data(pokemon["ability"])
                if ability_data:
                    ability_str = f", Ability: {ability_data['ability_name']}"
            
            item_str = ""
            if pokemon.get("item"):
                item_data = self.agent.db_tools.get_item_data(pokemon["item"])
                if item_data:
                    item_str = f", Item: {item_data['item_name']}"
            
            output.append(f"- {name} (HP: {hp_percent}%{status_str}{ability_str}{item_str})")
            
            # Add type matchups for team member
            if 'type_matchups' in pokemon_data:
                output.append("  Type Matchups:")
                weaknesses = [f"{t} ({m}x)" for t, m in pokemon_data['type_matchups']['defending'].items() if m > 1]
                resistances = [f"{t} ({m}x)" for t, m in pokemon_data['type_matchups']['defending'].items() if m < 1 and m > 0]
                immunities = [t for t, m in pokemon_data['type_matchups']['defending'].items() if m == 0]
                
                if weaknesses:
                    output.append(f"    Weak to: {', '.join(weaknesses)}")
                if resistances:
                    output.append(f"    Resists: {', '.join(resistances)}")
                if immunities:
                    output.append(f"    Immune to: {', '.join(immunities)}")
            
            # Add moves with details for team member
            if pokemon["moves"]:
                output.append("  Known moves:")
                for move_name in pokemon["moves"]:
                    move_data = self.agent.db_tools.get_move_data(move_name)
                    if move_data:
                        output.append(f"    - {move_data['move_name']} (Type: {move_data['type']}, "
                                    f"Power: {move_data['power']}, Accuracy: {move_data['accuracy']})")
                        output.append(f"      Description: {move_data['description']}")
            
            if pokemon.get("stats"):
                stats = [f"{stat.upper()}: {val}" for stat, val in pokemon["stats"].items() if val != 0]
                if stats:
                    output.append(f"  Stats: {', '.join(stats)}")
            
            if pokemon.get("tera_type"):
                output.append(f"  Tera Type: {pokemon['tera_type']}")
                if pokemon.get("terastallized"):
                    output.append("  Currently Terastallized")
        
        output.append("\nREVEALED OPPONENT POKEMON:")
        for name, pokemon in state["team"]["opponent"].items():
            # Get complete data for opponent's revealed Pokemon
            pokemon_data = self.agent.db_tools.get_pokemon_complete_data(name)
            
            # Handle fainted Pokemon case
            if pokemon["hp"] == "0" or pokemon["hp"] == "0 fnt" or "fnt" in pokemon["hp"]:
                hp_percent = 0
            else:
                try:
                    hp_val, max_hp = pokemon["hp"].split('/')
                    hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                except (ValueError, IndexError):
                    hp_percent = 0
                    print(f"Warning: Could not parse HP value: {pokemon['hp']}")
            
            status_str = f", Status: {pokemon['status']}" if pokemon["status"] else ""
            ability_str = ""
            if pokemon["ability"]:
                ability_data = self.agent.db_tools.get_ability_data(pokemon["ability"])
                if ability_data:
                    ability_str = ""
            if pokemon["ability"]:
                ability_data = self.agent.db_tools.get_ability_data(pokemon["ability"])
                if ability_data:
                    ability_str = f", Ability: {ability_data['ability_name']}"
            
            item_str = ""
            if pokemon.get("item"):
                item_data = self.agent.db_tools.get_item_data(pokemon["item"])
                if item_data:
                    item_str = f", Item: {item_data['item_name']}"
            
            output.append(f"- {name} (HP: {hp_percent}%{status_str}{ability_str}{item_str})")
            
            # Add type matchups for revealed opponent Pokemon
            if 'type_matchups' in pokemon_data:
                output.append("  Type Matchups:")
                weaknesses = [f"{t} ({m}x)" for t, m in pokemon_data['type_matchups']['defending'].items() if m > 1]
                resistances = [f"{t} ({m}x)" for t, m in pokemon_data['type_matchups']['defending'].items() if m < 1 and m > 0]
                immunities = [t for t, m in pokemon_data['type_matchups']['defending'].items() if m == 0]
                
                if weaknesses:
                    output.append(f"    Weak to: {', '.join(weaknesses)}")
                if resistances:
                    output.append(f"    Resists: {', '.join(resistances)}")
                if immunities:
                    output.append(f"    Immune to: {', '.join(immunities)}")
            
            # Add moves with details for revealed opponent Pokemon
            if pokemon["moves"]:
                output.append("  Known moves:")
                for move_name in pokemon["moves"]:
                    move_data = self.agent.db_tools.get_move_data(move_name)
                    if move_data:
                        output.append(f"    - {move_data['move_name']} (Type: {move_data['type']}, "
                                    f"Power: {move_data['power']}, Accuracy: {move_data['accuracy']})")
                        output.append(f"      Description: {move_data['description']}")
            
            if pokemon.get("stats"):
                stats = [f"{stat.upper()}: {val}" for stat, val in pokemon["stats"].items() if val != 0]
                if stats:
                    output.append(f"  Stats: {', '.join(stats)}")
            
            if pokemon.get("tera_type"):
                output.append(f"  Tera Type: {pokemon['tera_type']}")
                if pokemon.get("terastallized"):
                    output.append("  Currently Terastallized")
        
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
        
        # Available Actions with enhanced move information
        if state["waiting_for_decision"]:
            output.append("\nAVAILABLE ACTIONS:")
            if state["valid_moves"]:
                output.append("Available moves:")
                for move in state["valid_moves"]:
                    move_data = self.agent.db_tools.get_move_data(move['move'])
                    if move_data:
                        move_str = (f"- Move {move['index']}: {move_data['move_name']} "
                                f"(Type: {move_data['type']}, Power: {move_data['power']}, "
                                f"Accuracy: {move_data['accuracy']}, PP: {move['pp']}/{move['maxpp']})")
                        if move.get('can_tera'):
                            move_str += " [Can Terastallize with 'move Xt']"
                        output.append(move_str)
                        output.append(f"  Description: {move_data['description']}")
                    else:
                        # Fallback if move data not found
                        move_str = f"- Move {move['index']}: {move['move']} (PP: {move['pp']}/{move['maxpp']})"
                        if move.get('can_tera'):
                            move_str += " [Can Terastallize with 'move Xt']"
                        output.append(move_str)
            
            if state["valid_switches"]:
                output.append("\nAvailable switches:")
                for switch in state["valid_switches"]:
                    # Get complete data for switch Pokemon
                    switch_pokemon_data = self.agent.db_tools.get_pokemon_complete_data(switch['pokemon'])
                    output.append(f"- Switch {switch['index']}: {switch['pokemon']} ({switch['condition']})")
                    
                    # Add type matchups for switch options
                    if 'type_matchups' in switch_pokemon_data:
                        weaknesses = [f"{t} ({m}x)" for t, m in switch_pokemon_data['type_matchups']['defending'].items() if m > 1]
                        resistances = [f"{t} ({m}x)" for t, m in switch_pokemon_data['type_matchups']['defending'].items() if m < 1 and m > 0]
                        immunities = [t for t, m in switch_pokemon_data['type_matchups']['defending'].items() if m == 0]
                        
                        if weaknesses:
                            output.append(f"    Weak to: {', '.join(weaknesses)}")
                        if resistances:
                            output.append(f"    Resists: {', '.join(resistances)}")
                        if immunities:
                            output.append(f"    Immune to: {', '.join(immunities)}")
        
        output.append("\n=== END BATTLE SITUATION ===")
        return "\n".join(output)

    async def start(self):
        """Start the battle manager and establish connection to Pokemon Showdown"""
        try:
            self.logger.info("Starting battle manager")
            self.is_running = True
            self.battle_concluded = False
            await self.bot.connect()
            
            receive_task = asyncio.create_task(self.bot.receive_messages())
            battle_task = asyncio.create_task(self.run_battle_loop())
            
            try:
                done, pending = await asyncio.wait(
                    [receive_task, battle_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
            except Exception as e:
                self.logger.error(f"Error in tasks: {str(e)}")
                raise
            finally:
                self.logger.info("Battle manager stopping, returning control to system manager")
                
        except Exception as e:
            self.logger.error(f"Error in battle manager: {str(e)}", exc_info=True)
            raise

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
        try:
            # Format the battle state with Pokemon context
            formatted_state = self.parse_battle_state(state)
            
            # Create the query for the agent with explicit formatting instructions
            query = f"""Based on the following battle situation, what would be the best move to make? Consider all available moves and switches.

            {formatted_state}

            Analyze the situation and explain your reasoning. Then, provide your chosen move in a separate line starting with "CHOSEN MOVE:".
            For example:
            - If choosing a regular move, write "CHOSEN MOVE: move X" (e.g., "CHOSEN MOVE: move 1")
            - If choosing to terastallize with a move, write "CHOSEN MOVE: move Xt" (e.g., "CHOSEN MOVE: move 1t")
            - If choosing to switch, write "CHOSEN MOVE: switch X" (e.g., "CHOSEN MOVE: switch 3")

            Make sure to consider terastallizing when it would be advantageous and available.
            Make sure to separate your analysis from your move choice with a blank line."""

            # Get the agent's response
            response = self.agent.run(query)
            if not response:
                print("Warning: Received empty response from agent")
                return "No analysis provided.", None
            
            try:
                parts = response.split("CHOSEN MOVE:")
                
                if len(parts) != 2:
                    print(f"Warning: Agent response not properly formatted: {response}")
                    return response, None
                    
                reasoning = parts[0].strip()
                move_command = parts[1].strip().lower()
                
                # Validate move command format
                if not (move_command.startswith("move ") or move_command.startswith("switch ")):
                    print(f"Warning: Invalid move command format: {move_command}")
                    return reasoning, None
                    
                print("\nAgent's analysis:")
                print(reasoning)
                print(f"\nChosen move: {move_command}")
                
                # Add turn update to chat history if available
                if hasattr(self, 'system_manager') and self.system_manager and self.battle_id:
                    # Format the turn message more clearly
                    turn_message = (
                        f"Analysis:\n"
                        f"{reasoning}\n\n"
                        f"Chosen Move: {move_command}"
                    )
                    
                    turn_data = {
                        'analysis': reasoning,
                        'move': move_command
                    }
                    
                    self.system_manager.chat_history.add_battle_turn(
                        self.battle_id,
                        turn_data,
                        turn_message
                    )
                
                return reasoning, move_command
                
            except Exception as e:
                print(f"Error parsing agent response: {str(e)}")
                print("Raw response:", response)
                return str(response), None
                
        except Exception as e:
            print(f"Error in get_agent_decision: {str(e)}")
            return f"Error occurred: {str(e)}", None

    async def run_battle_loop(self):
        """Main loop that monitors the battle state and handles moves"""
        try:
            self.logger.info("Starting battle loop")
            self.battle_id = datetime.now().strftime("%Y%m%d%H%M%S")
            
            last_state_hash = None
            
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
                                if hasattr(self, 'system_manager') and self.system_manager:
                                    self.system_manager.chat_history.add_battle_turn(
                                        self.battle_id,
                                        {'error': result['error']},
                                        f"Move execution failed: {result['error']}"
                                    )
                    
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.logger.error(f"Error in battle loop: {str(e)}", exc_info=True)
            self.is_running = False
            raise


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