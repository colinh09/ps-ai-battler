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

    async def handle_battle_end(self, final_state: Dict, battle_history: str):
        """Handle battle end and trigger analysis"""
        # Add a flag to prevent duplicate handling
        if self.battle_concluded:
            return
            
        self.logger.info("Battle has concluded, preparing analysis")
        self.battle_concluded = True
        self.is_running = False
        
        try:
            # Send immediate "analyzing" message
            await self.bot.send_pm(
                self.bot.target_username,
                "Analyzing battle results..."
            )
            
            # Generate analysis using the provided state and history
            if final_state and battle_history:
                analysis = await self.get_battle_analysis(final_state, battle_history)
                
                if analysis:
                    await self.bot.send_pm(self.bot.target_username, analysis)
        except Exception as e:
            self.logger.error(f"Error in battle end analysis: {str(e)}")
            print(f"Error generating battle analysis: {str(e)}")

    async def get_battle_analysis(self, final_state: Dict, battle_history: str) -> str:
        """Get agent's analysis of the completed battle"""
        query = f"""Analyze this completed Pokemon battle. Review the battle history and final state to provide insights.

        Battle History:
        {battle_history}

        Final Battle State:
        {self.parse_battle_state(final_state)}

        Please provide:
        1. An overview of how the battle progressed
        2. Key turning points or critical moments
        3. Effective strategies that were used
        4. Areas for improvement
        5. Notable matchups and how they influenced the battle
        
        Focus on constructive analysis that could help improve future battles.
        Provide the analysis in paragraph format. Do not include headers.
        """

        # Make sure agent.run is awaited properly
        analysis = self.agent.run(query)
        return analysis


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
        
        # YOUR ACTIVE POKEMON section
        if state["active"]["self"]:
            pokemon = state["active"]["self"]
            
            # Get base stats and other data from database
            pokemon_data = self.agent.db_tools.get_pokemon_complete_data(pokemon['name'])
            
            # Calculate HP percentage
            if pokemon["hp"] == "0" or pokemon["hp"] == "0 fnt" or "fnt" in pokemon["hp"]:
                hp_percent = 0
            else:
                try:
                    hp_val, max_hp = pokemon["hp"].split('/')
                    hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                except (ValueError, IndexError):
                    hp_percent = 0
            
            output.append("YOUR ACTIVE POKEMON:")
            output.append(f"- {pokemon['name']} (HP: {hp_percent}%)")
            
            # Add Role
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
            
            # Add moves (without duplication)
            if pokemon["moves"]:
                output.append("  Known moves:")
                # Use a set to prevent duplicate moves
                seen_moves = set()
                for move_name in pokemon["moves"]:
                    if move_name not in seen_moves:
                        seen_moves.add(move_name)
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
            
            # Add base stats from pokemon_data
            if pokemon_data:
                output.append("  Base Stats:")
                output.append(f"    HP: {pokemon_data['hp']}")
                output.append(f"    Attack: {pokemon_data['atk']}")
                output.append(f"    Defense: {pokemon_data['def']}")
                output.append(f"    Sp. Attack: {pokemon_data['spa']}")
                output.append(f"    Sp. Defense: {pokemon_data['spd']}")
                output.append(f"    Speed: {pokemon_data['spe']}")
            
            # Add Tera Type info
            if pokemon.get("tera_type"):
                output.append(f"  Tera Type: {pokemon['tera_type']}")
                if pokemon.get("terastallized"):
                    output.append("  Currently Terastallized")
                elif not state.get("tera_used", False):
                    output.append("  Can Terastallize")
            
            # Add current stats
            if pokemon.get("stats"):
                output.append("  Current Stats:")
                stats = [f"{stat.upper()}: {val}" for stat, val in pokemon["stats"].items() if val != 0]
                if stats:
                    output.append(f"    {', '.join(stats)}")

        # OPPONENT'S ACTIVE POKEMON section
        if state["active"]["opponent"]:
            pokemon = state["active"]["opponent"]
            pokemon_data = self.agent.db_tools.get_pokemon_complete_data(pokemon['name'])
            
            output.append("\nOPPONENT'S ACTIVE POKEMON:")
            
            # Calculate HP percentage
            if pokemon["hp"] == "0" or pokemon["hp"] == "0 fnt" or "fnt" in pokemon["hp"]:
                hp_percent = 0
            else:
                try:
                    hp_val, max_hp = pokemon["hp"].split('/')
                    hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                except (ValueError, IndexError):
                    hp_percent = 0
            
            output.append(f"- {pokemon['name']} (HP: {hp_percent}%)")
            
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
            
            # Add base stats from pokemon_data
            if pokemon_data:
                output.append("  Base Stats:") 
                output.append(f"    HP: {pokemon_data.get('hp', 'Unknown')}")
                output.append(f"    Attack: {pokemon_data.get('atk', 'Unknown')}")
                output.append(f"    Defense: {pokemon_data.get('def', 'Unknown')}")
                output.append(f"    Sp. Attack: {pokemon_data.get('spa', 'Unknown')}")
                output.append(f"    Sp. Defense: {pokemon_data.get('spd', 'Unknown')}")
                output.append(f"    Speed: {pokemon_data.get('spe', 'Unknown')}")
            
            # Add possibilities from random battle data
            rbd = pokemon_data.get('random_battle_data', {})
            if rbd.get('roles'):
                output.append(f"  Possible Roles: {', '.join(rbd['roles'])}")
            if rbd.get('level'):
                output.append(f"  Level: {rbd['level']}")
            if rbd.get('abilities'):
                output.append(f"  Possible Abilities: {', '.join(rbd['abilities'])}")
            if rbd.get('items'):
                output.append(f"  Possible Items: {', '.join(rbd['items'])}")
            if rbd.get('moves'):
                output.append(f"  Possible Moves: {', '.join(rbd['moves'])}")
            if rbd.get('tera_types'):
                output.append(f"  Possible Tera Types: {', '.join(rbd['tera_types'])}")
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
            
            # Add basic info
            output.append(f"- {name} (HP: {hp_percent}%)")
            
            # Add Role from random_battle_data
            if 'random_battle_data' in pokemon_data and pokemon_data['random_battle_data'].get('roles'):
                output.append(f"  Role: {', '.join(pokemon_data['random_battle_data']['roles'])}")
            
            # Add ability info with description
            if pokemon.get("ability"):
                ability_data = self.agent.db_tools.get_ability_data(pokemon["ability"])
                if ability_data:
                    output.append(f"  Ability: {ability_data['ability_name']}")
                    output.append(f"    Description: {ability_data['description']}")
            
            # Add item info with description
            if pokemon.get("item"):
                item_data = self.agent.db_tools.get_item_data(pokemon["item"])
                if item_data:
                    output.append(f"  Item: {item_data['item_name']}")
                    output.append(f"    Description: {item_data['description']}")
            
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
            
            # Add moves with details
            if pokemon["moves"]:
                output.append("  Known moves:")
                seen_moves = set()
                for move_name in pokemon["moves"]:
                    if move_name not in seen_moves:
                        seen_moves.add(move_name)
                        move_data = self.agent.db_tools.get_move_data(move_name)
                        if move_data:
                            output.append(f"    - {move_data['move_name']} (Type: {move_data['type']}, "
                                        f"Power: {move_data['power']}, Accuracy: {move_data['accuracy']})")
                            output.append(f"      Description: {move_data['description']}")
            
            # Add base stats
            if pokemon_data:
                output.append("  Base Stats:")
                output.append(f"    HP: {pokemon_data['hp']}")
                output.append(f"    Attack: {pokemon_data['atk']}")
                output.append(f"    Defense: {pokemon_data['def']}")
                output.append(f"    Sp. Attack: {pokemon_data['spa']}")
                output.append(f"    Sp. Defense: {pokemon_data['spd']}")
                output.append(f"    Speed: {pokemon_data['spe']}")
            
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
            
            # Add basic info
            status_str = f", Status: {pokemon['status']}" if pokemon["status"] else ""
            output.append(f"- {name} (HP: {hp_percent}%{status_str})")
            
            # Add Role from random_battle_data
            if 'random_battle_data' in pokemon_data and pokemon_data['random_battle_data'].get('roles'):
                output.append(f"  Role: {', '.join(pokemon_data['random_battle_data']['roles'])}")
            
            # Add ability info with description
            if pokemon["ability"]:
                ability_data = self.agent.db_tools.get_ability_data(pokemon["ability"])
                if ability_data:
                    output.append(f"  Ability: {ability_data['ability_name']}")
                    output.append(f"    Description: {ability_data['description']}")
            
            # Add item info with description
            if pokemon.get("item"):
                item_data = self.agent.db_tools.get_item_data(pokemon["item"])
                if item_data:
                    output.append(f"  Item: {item_data['item_name']}")
                    output.append(f"    Description: {item_data['description']}")
            
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
            
            # Add moves with details
            if pokemon["moves"]:
                output.append("  Known moves:")
                for move_name in pokemon["moves"]:
                    move_data = self.agent.db_tools.get_move_data(move_name)
                    if move_data:
                        output.append(f"    - {move_data['move_name']} (Type: {move_data['type']}, "
                                    f"Power: {move_data['power']}, Accuracy: {move_data['accuracy']})")
                        output.append(f"      Description: {move_data['description']}")
            
            # Add base stats
            if pokemon_data:
                output.append("  Base Stats:")
                output.append(f"    HP: {pokemon_data['hp']}")
                output.append(f"    Attack: {pokemon_data['atk']}")
                output.append(f"    Defense: {pokemon_data['def']}")
                output.append(f"    Sp. Attack: {pokemon_data['spa']}")
                output.append(f"    Sp. Defense: {pokemon_data['spd']}")
                output.append(f"    Speed: {pokemon_data['spe']}")
            
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
            output.append("\nAVAILABLE ACTIONS (You MUST choose ONLY from these actions):")
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

    async def get_agent_decision(self, state: Dict, previous_error: Optional[str] = None, exclude_switches: bool = False) -> tuple[str, Optional[str]]:
        """
        Get the agent's decision based on the current battle state.
        
        Args:
            state (Dict): Current battle state
            previous_error (str, optional): Error message from previous attempt
            exclude_switches (bool): Whether to exclude switch options from prompt
            
        Returns:
            tuple[str, Optional[str]]: (reasoning, move_command)
        """
        try:
            formatted_state = self.parse_battle_state(state)
            battle_history = self.bot.get_battle_history_text() if hasattr(self.bot, 'get_battle_history_text') else ""
            # Build the query with error context if present
            error_context = ""
            if previous_error:
                error_context = f"\nPrevious attempt failed because: {previous_error}\n"

            # Base query
            query = f"""Based on the following battle situation, what would be the best move to make? Consider {"only moves, no switching allowed" if exclude_switches else "all available moves and switches"}.
            
            Battle History:
            {battle_history}
            
            {error_context}
            {formatted_state}

            Analyze the situation and explain your reasoning. Then, provide your chosen move in a separate line starting with "CHOSEN MOVE:".
            For example:
            - If choosing a regular move, write "CHOSEN MOVE: move X" (e.g., "CHOSEN MOVE: move 1")
            - If choosing to terastallize with a move, write "CHOSEN MOVE: move Xt" (e.g., "CHOSEN MOVE: move 1t")"""

            # Only add switch example if switches aren't excluded
            if not exclude_switches:
                query += '\n        - If choosing to switch, write "CHOSEN MOVE: switch X" (e.g., "CHOSEN MOVE: switch 3")'

            query += "\n\nMake sure to consider terastallizing when it would be advantageous and available."
            query += "\nMake sure to separate your analysis from your move choice with a blank line."
            query += "\nOnly choose from the explicitly listed available moves and switches above."

            # Get and parse response
            response = self.agent.run(query)
            if not response:
                return "No analysis provided.", None
            
            try:
                parts = response.split("CHOSEN MOVE:")
                
                if len(parts) != 2:
                    print(f"Warning: Agent response not properly formatted: {response}")
                    return response, None
                    
                reasoning = parts[0].strip()
                move_command = parts[1].strip().lower()
                
                # Validate move command format
                if exclude_switches and move_command.startswith("switch"):
                    # If we excluded switches but got a switch command, retry without switches
                    return await self.get_agent_decision(state, "Switching is not allowed at this time.", True)
                
                if not (move_command.startswith("move ") or (not exclude_switches and move_command.startswith("switch "))):
                    print(f"Warning: Invalid move command format: {move_command}")
                    return await self.get_agent_decision(state, "Invalid move format. Please use the exact format shown.", exclude_switches)
                    
                return reasoning, move_command
                
            except Exception as e:
                print(f"Error parsing agent response: {str(e)}")
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
                if self.battle_concluded:
                    self.logger.info("Battle has ended, exiting battle loop")
                    self.is_running = False
                    return  # Exit immediately
                    
                new_state = self.get_current_state()
                if not new_state:  # If no state, battle might have ended
                    await asyncio.sleep(0.5)
                    continue
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
                        print("MOVE COMMAND: ", move_command)
                        
                        # Send the reasoning to the battle chat
                        if reasoning:
                            await self.bot.send_battle_message(reasoning)

                        max_retries = 3
                        retry_count = 0
                        
                        while move_command and retry_count < max_retries and not self.battle_concluded:
                            # Check if battle has ended before making move
                            if self.battle_concluded:
                                self.logger.info("Battle ended during move attempts, stopping retries")
                                break
                                
                            result = await self.make_move(move_command)
                            
                            if result["success"]:
                                await self.bot.send_battle_message(f"Making move: {move_command}")
                                break  # Exit retry loop on success
                            else:
                                # Check again if battle ended after failed move
                                if self.battle_concluded:
                                    self.logger.info("Battle ended after move attempt, stopping retries")
                                    break
                                    
                                print(f"Move execution failed: {result['error']}")
                                await self.bot.send_battle_message(f"Move failed: {result['error']}")
                                
                                # Decide whether to exclude switches based on error
                                exclude_switches = (
                                    'trapped' in result['error'].lower() or 
                                    'switch' in result['error'].lower()
                                )
                                
                                # Get new analysis and move
                                reasoning, move_command = await self.get_agent_decision(
                                    new_state,
                                    result['error'],
                                    exclude_switches=exclude_switches
                                )
                                
                                # Send the new reasoning to chat
                                if reasoning and not self.battle_concluded:
                                    await self.bot.send_battle_message(reasoning)
                                
                                retry_count += 1
                            
                            # Add small delay between retries
                            await asyncio.sleep(0.5)
                        
                        if retry_count >= max_retries and not self.battle_concluded:
                            error_msg = "Failed to get valid move after maximum retries"
                            print(error_msg)
                            await self.bot.send_battle_message(error_msg)
                
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