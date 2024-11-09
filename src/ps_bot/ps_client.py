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
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

@dataclass
class Pokemon:
    name: str
    hp: str = "100/100"
    status: Optional[str] = None
    ability: Optional[str] = None
    moves: Set[str] = field(default_factory=set)
    volatile_status: List[str] = field(default_factory=list)
    boosts: Dict[str, int] = field(default_factory=lambda: {
        "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0
    })
    tera_type: Optional[str] = None
    revealed: bool = False
    # New fields
    item: Optional[str] = None
    terastallized: bool = False
    can_terastallize: bool = False
    stats: Dict[str, int] = field(default_factory=lambda: {
        "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0
    })

@dataclass
class BattleState:
    active_pokemon: Dict[str, Pokemon]
    team_pokemon: Dict[str, Dict[str, Pokemon]]
    field_conditions: Dict[str, any]
    side_conditions: Dict[str, Dict[str, list]]
    
    @classmethod
    def create_initial_state(cls):
        return cls(
            active_pokemon={
                "p1": None,
                "p2": None
            },
            team_pokemon={
                "p1": {},
                "p2": {}
            },
            field_conditions={
                "weather": None,
                "terrain": None,
                "trick_room": False,
                "tailwind": {"p1": False, "p2": False}
            },
            side_conditions={
                "p1": {
                    "hazards": [],
                    "screens": []
                },
                "p2": {
                    "hazards": [],
                    "screens": []
                }
            }
        )

class ShowdownBot:
    def __init__(self, username: str, password: str, target_username: str):
        self.ws = None
        self.username = username
        self.password = password
        self.target_username = target_username
        self.websocket_url = "wss://sim3.psim.us/showdown/websocket"
        self.current_battle = None
        self.battle_state = BattleState.create_initial_state()
        self.waiting_for_decision = False
        self.is_team_preview = False
        self.player_id = None  # Will be set to "p1" or "p2" during battle
        self.current_request = None  # Store the current request for move validation
        
    def get_opponent_id(self):
        return "p2" if self.player_id == "p1" else "p1"

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

    def print_battle_state(self):
        """Print current battle state for debugging with improved HP display"""
        print("\n=== Current Battle State ===")
        print("\nActive Pokemon:")
        for player in ["p1", "p2"]:
            if self.battle_state.active_pokemon[player]:
                poke = self.battle_state.active_pokemon[player]
                # Convert HP to percentage
                hp_val = poke.hp.split('/')[0]
                max_hp = poke.hp.split('/')[1]
                hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                
                print(f"{player}: {poke.name} (HP: {hp_percent}%, Status: {poke.status})")
                if poke.ability:
                    print(f"  Ability: {poke.ability}")
                if poke.item:
                    print(f"  Item: {poke.item}")
                if poke.moves:
                    print(f"  Known moves: {', '.join(poke.moves)}")
                if poke.boosts:
                    boosts = [f"{stat}: {val:+d}" for stat, val in poke.boosts.items() if val != 0]
                    if boosts:
                        print(f"  Boosts: {', '.join(boosts)}")
                if poke.stats:
                    print(f"  Stats: {', '.join(f'{stat}: {val}' for stat, val in poke.stats.items())}")
                if poke.tera_type:
                    print(f"  Tera Type: {poke.tera_type}")
                    if poke.terastallized:
                        print("  Currently Terastallized")
                    elif poke.can_terastallize:
                        print("  Can Terastallize")

        print("\nTeam Pokemon:")
        for player in ["p1", "p2"]:
            print(f"\n{player} team:")
            for poke_name, poke in self.battle_state.team_pokemon[player].items():
                # Convert HP to percentage
                hp_val = poke.hp.split('/')[0]
                max_hp = poke.hp.split('/')[1]
                hp_percent = round((float(hp_val) / float(max_hp)) * 100, 1)
                
                status_str = f", Status: {poke.status}" if poke.status else ""
                ability_str = f", Ability: {poke.ability}" if poke.ability else ""
                item_str = f", Item: {poke.item}" if poke.item else ""
                print(f"  {poke_name} (HP: {hp_percent}%{status_str}{ability_str}{item_str})")
                if poke.moves:
                    print(f"    Known moves: {', '.join(poke.moves)}")
                if poke.stats:
                    print(f"    Stats: {', '.join(f'{stat}: {val}' for stat, val in poke.stats.items())}")
                if poke.tera_type:
                    print(f"    Tera Type: {poke.tera_type}")
                    if poke.terastallized:
                        print("    Currently Terastallized")

        print("\nField Conditions:")
        weather = self.battle_state.field_conditions["weather"]
        terrain = self.battle_state.field_conditions["terrain"]
        trick_room = self.battle_state.field_conditions["trick_room"]
        
        if weather:
            print(f"  Weather: {weather}")
        if terrain:
            print(f"  Terrain: {terrain}")
        if trick_room:
            print(f"  Trick Room is active")
        if not weather and not terrain and not trick_room:
            print("  None")

        print("\nSide Conditions:")
        for player in ["p1", "p2"]:
            conditions = self.battle_state.side_conditions[player]
            if conditions["hazards"] or conditions["screens"]:
                print(f"  {player}:")
                if conditions["hazards"]:
                    print(f"    Hazards: {', '.join(conditions['hazards'])}")
                if conditions["screens"]:
                    print(f"    Screens: {', '.join(conditions['screens'])}")
        print("\n=========================\n")

    def update_pokemon_info(self, player: str, details: str, condition: str) -> None:
        """Update Pokemon information from battle messages"""
        name = details.split(',')[0]
        
        # Create Pokemon if it doesn't exist in the team
        if name not in self.battle_state.team_pokemon[player]:
            self.battle_state.team_pokemon[player][name] = Pokemon(name=name)
        
        pokemon = self.battle_state.team_pokemon[player][name]
        pokemon.revealed = True
        
        # Update HP and status
        if condition == "0 fnt":
            pokemon.hp = "0/100"
        else:
            hp_parts = condition.split()
            pokemon.hp = hp_parts[0]
            if len(hp_parts) > 1:
                pokemon.status = hp_parts[1]

    async def handle_switch(self, player: str, pokemon_details: str, condition: str):
        """Handle Pokemon switching"""
        self.update_pokemon_info(player, pokemon_details, condition)
        name = pokemon_details.split(',')[0]
        
        # Update active Pokemon
        self.battle_state.active_pokemon[player] = self.battle_state.team_pokemon[player][name]
        
        # Reset volatile status and boosts for the switched-in Pokemon
        self.battle_state.active_pokemon[player].volatile_status = []
        self.battle_state.active_pokemon[player].boosts = {
            "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0
        }

    async def make_move(self, move_index: int) -> bool:
        """Try to make a move with the given index"""
        if not self.current_battle or not self.waiting_for_decision:
            return False
            
        move_cmd = f"{self.current_battle}|/choose move {move_index}"
        await self.ws.send(move_cmd)
        self.waiting_for_decision = False
        return True

    async def make_switch(self, pokemon_index: int) -> bool:
        """Try to switch to the Pokemon at the given index"""
        if not self.current_battle or not self.waiting_for_decision:
            return False
            
        switch_cmd = f"{self.current_battle}|/choose switch {pokemon_index}"
        await self.ws.send(switch_cmd)
        self.waiting_for_decision = False
        return True

    def print_available_options(self):
        """Print available moves and switches in a clear format"""
        print("\n=== Available Options ===")
        
        # Print available moves
        valid_moves = self.get_valid_moves()
        if valid_moves:
            print("\nAvailable Moves:")
            for move in valid_moves:
                print(f"  {move['index']}. {move['move']} (Type: {move['type']}, PP: {move['pp']}/{move['maxpp']})")
        
        # Print available switches
        valid_switches = self.get_valid_switches()
        if valid_switches:
            print("\nAvailable Switches:")
            for switch in valid_switches:
                print(f"  {switch['index']}. {switch['pokemon']} ({switch['condition']})")
        
        if not valid_moves and not valid_switches:
            print("\nNo valid moves or switches available!")
        
        print("\nEnter 'move X' to use a move or 'switch X' to switch Pokemon (e.g., 'move 1' or 'switch 2')")
        print("======================")

    async def handle_battle_message(self, room_id: str, message: str):
        """Handle messages from a battle room with improved hazard tracking"""
        try:
            # Handle battle initialization
            if "|init|battle" in message:
                self.current_battle = room_id.strip('>')
                self.battle_state = BattleState.create_initial_state()
                print(f"Joined battle room: {self.current_battle}")
                await self.ws.send(f"|/join {self.current_battle}")
            
            # Parse each line of the message
            for line in message.split('\n'):
                parts = line.strip().split('|')
                if len(parts) < 2:
                    continue
                    
                command = parts[1]
                
                # Handle different message types
                if command == "player":
                    if parts[2] == "p1" and parts[3] == self.username:
                        self.player_id = "p1"
                    elif parts[2] == "p2" and parts[3] == self.username:
                        self.player_id = "p2"
                
                elif command == "poke":
                    player = parts[2]
                    pokemon_details = parts[3]
                    name = pokemon_details.split(',')[0]
                    if name not in self.battle_state.team_pokemon[player]:
                        self.battle_state.team_pokemon[player][name] = Pokemon(name=name)
                
                elif command == "switch" or command == "drag":
                    player = parts[2][:2]
                    await self.handle_switch(player, parts[3], parts[4])
                
                elif command == "move":
                    player = parts[2][:2]
                    move = parts[3]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].moves.add(move)
                
                elif command == "-damage" or command == "-heal":
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].hp = parts[3].split()[0]
                        if len(parts[3].split()) > 1:
                            self.battle_state.active_pokemon[player].status = parts[3].split()[1]
                
                elif command == "-status":
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].status = parts[3]
                
                elif command == "-ability":
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].ability = parts[3]
                
                elif command in ["-boost", "-unboost"]:
                    player = parts[2][:2]
                    stat = parts[3]
                    amount = int(parts[4]) * (1 if command == "-boost" else -1)
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].boosts[stat] += amount
                
                elif command == "-weather":
                    weather = parts[2] if parts[2] != "none" else None
                    self.battle_state.field_conditions["weather"] = weather

                elif command == "-fieldstart":
                    if "trick room" in parts[3].lower():
                        self.battle_state.field_conditions["trick_room"] = True
                    elif "terrain" in parts[3].lower():
                        self.battle_state.field_conditions["terrain"] = parts[3]
                    
                elif command == "-fieldend":
                    if "trick room" in parts[3].lower():
                        self.battle_state.field_conditions["trick_room"] = False
                    elif "terrain" in parts[3].lower():
                        self.battle_state.field_conditions["terrain"] = None
                
                elif command == "-sidestart":
                    player = parts[2][:2]
                    condition = parts[3]
                    
                    # Handle hazards
                    if any(hazard in condition.lower() for hazard in ["spikes", "stealth rock", "toxic spikes", "sticky web"]):
                        self.battle_state.side_conditions[player]["hazards"].append(condition)
                    # Handle screens
                    elif any(screen in condition.lower() for screen in ["reflect", "light screen", "aurora veil"]):
                        self.battle_state.side_conditions[player]["screens"].append(condition)
                    
                elif command == "-sideend":
                    player = parts[2][:2]
                    condition = parts[3]
                    
                    # Remove ended conditions
                    if any(hazard in condition.lower() for hazard in ["spikes", "stealth rock", "toxic spikes", "sticky web"]):
                        if condition in self.battle_state.side_conditions[player]["hazards"]:
                            self.battle_state.side_conditions[player]["hazards"].remove(condition)
                    elif any(screen in condition.lower() for screen in ["reflect", "light screen", "aurora veil"]):
                        if condition in self.battle_state.side_conditions[player]["screens"]:
                            self.battle_state.side_conditions[player]["screens"].remove(condition)
                
                elif command == "faint":
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].hp = "0/100"
                
                elif command == "win":
                    winner = parts[2]
                    print(f"Battle ended! Winner: {winner}")
                    self.current_battle = None
                    await asyncio.sleep(2)
                    await self.challenge_player()
                
                elif command == "request":
                    if not parts[2]:
                        continue
                    
                    request = json.loads(parts[2])
                    self.current_request = request
                    
                    # Update Pokemon information from request
                    if "side" in request:
                        for pokemon_data in request["side"]["pokemon"]:
                            name = pokemon_data["ident"].split(": ")[1]
                            if name in self.battle_state.team_pokemon[self.player_id]:
                                pokemon = self.battle_state.team_pokemon[self.player_id][name]
                                pokemon.item = pokemon_data.get("item")
                                pokemon.hp = pokemon_data.get("condition", "100/100")
                                pokemon.stats = pokemon_data.get("stats", {})
                                pokemon.tera_type = pokemon_data.get("teraType")
                                pokemon.terastallized = bool(pokemon_data.get("terastallized"))
                    
                    # Update terastallize availability for active Pokemon
                    if "active" in request and request["active"]:
                        active_data = request["active"][0]
                        active_pokemon = self.battle_state.active_pokemon[self.player_id]
                        if active_pokemon:
                            active_pokemon.can_terastallize = "canTerastallize" in active_data
                    
                    self.print_battle_state()
                    # Add a small delay to let all state updates complete
                    await asyncio.sleep(0.1)
                    
                    if "forceSwitch" in request and request["forceSwitch"][0]:
                        self.waiting_for_decision = True
                        print("\nForce switch required!")
                        self.print_available_options()
                        
                    elif "active" in request and request["active"]:
                        self.waiting_for_decision = True
                        print("\nMove required!")
                        self.print_available_options()
                
                elif command == "error":
                    print(f"Received error: {line}")
                    self.waiting_for_decision = True
        
        except Exception as e:
            print(f"Error in handle_battle_message: {str(e)}")
            print(f"Message was: {message}")

    async def receive_messages(self):
        """Main message handling loop"""
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
            sys.exit(1)

    async def challenge_player(self):
        """Send a Random Battle challenge to the target player"""
        print(f"Challenging {self.target_username} to a Random Battle...")
        challenge_cmd = f"|/challenge {self.target_username}, gen9randombattle"
        await self.ws.send(challenge_cmd)
                
    async def login(self, challstr):
        """Login to Pokemon Showdown"""
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
            await self.ws.send(f"|/avatar 225")
            
        except requests.exceptions.RequestException as e:
            print(f"Error during login request: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Error during login: {str(e)}")
            sys.exit(1)

    async def start(self):
        """Start the bot"""
        await self.connect()
        await self.receive_messages()

    def get_valid_moves(self) -> List[Dict]:
        """Get list of valid moves from the current request"""
        if not self.current_request or "active" not in self.current_request or not self.current_request["active"]:
            return []
            
        active = self.current_request["active"][0]
        if "moves" not in active:
            return []
            
        valid_moves = []
        for i, move in enumerate(active["moves"], 1):
            if not move.get("disabled", False):
                valid_moves.append({
                    "index": i,
                    "move": move["move"],
                    "type": move.get("type"),
                    "pp": move.get("pp", 0),
                    "maxpp": move.get("maxpp", 0)
                })
        return valid_moves

    def get_valid_switches(self) -> List[Dict]:
        """Get list of valid switches from current request"""
        if not self.current_request or "side" not in self.current_request:
            return []
            
        valid_switches = []
        for i, pokemon in enumerate(self.current_request["side"]["pokemon"], 1):
            if (not pokemon.get("active", False) and  # Can't switch to active Pokemon
                not pokemon.get("fainted", False)):   # Can't switch to fainted Pokemon
                valid_switches.append({
                    "index": i,
                    "pokemon": pokemon["ident"].split(": ")[1],
                    "details": pokemon.get("details", ""),
                    "condition": pokemon.get("condition", "")
                })
        return valid_switches

    def get_game_state(self) -> Dict:
        """Get current game state in a format suitable for the agent"""
        state = {
            "active": {
                "self": None,
                "opponent": None
            },
            "team": {
                "self": {},
                "opponent": {}
            },
            "field_conditions": self.battle_state.field_conditions,
            "side_conditions": {
                "self": self.battle_state.side_conditions[self.player_id],
                "opponent": self.battle_state.side_conditions[self.get_opponent_id()]
            },
            "waiting_for_decision": self.waiting_for_decision,
            "valid_moves": self.get_valid_moves(),
            "valid_switches": self.get_valid_switches()
        }
        
        # Add active Pokemon info
        if self.battle_state.active_pokemon[self.player_id]:
            state["active"]["self"] = {
                "name": self.battle_state.active_pokemon[self.player_id].name,
                "hp": self.battle_state.active_pokemon[self.player_id].hp,
                "status": self.battle_state.active_pokemon[self.player_id].status,
                "ability": self.battle_state.active_pokemon[self.player_id].ability,
                "moves": list(self.battle_state.active_pokemon[self.player_id].moves),
                "boosts": self.battle_state.active_pokemon[self.player_id].boosts,
                "volatile_status": self.battle_state.active_pokemon[self.player_id].volatile_status
            }
            
        if self.battle_state.active_pokemon[self.get_opponent_id()]:
            state["active"]["opponent"] = {
                "name": self.battle_state.active_pokemon[self.get_opponent_id()].name,
                "hp": self.battle_state.active_pokemon[self.get_opponent_id()].hp,
                "status": self.battle_state.active_pokemon[self.get_opponent_id()].status,
                "ability": self.battle_state.active_pokemon[self.get_opponent_id()].ability,
                "moves": list(self.battle_state.active_pokemon[self.get_opponent_id()].moves),
                "boosts": self.battle_state.active_pokemon[self.get_opponent_id()].boosts,
                "volatile_status": self.battle_state.active_pokemon[self.get_opponent_id()].volatile_status
            }
            
        # Add team Pokemon info
        for name, pokemon in self.battle_state.team_pokemon[self.player_id].items():
            state["team"]["self"][name] = {
                "hp": pokemon.hp,
                "status": pokemon.status,
                "ability": pokemon.ability,
                "moves": list(pokemon.moves)
            }
            
        for name, pokemon in self.battle_state.team_pokemon[self.get_opponent_id()].items():
            if pokemon.revealed:  # Only include revealed opponent Pokemon
                state["team"]["opponent"][name] = {
                    "hp": pokemon.hp,
                    "status": pokemon.status,
                    "ability": pokemon.ability,
                    "moves": list(pokemon.moves)
                }
                
        return state

    async def handle_instruction(self, instruction: str) -> Dict:
        """Handle an instruction from the agent"""
        if not self.waiting_for_decision:
            return {
                "success": False,
                "error": "Not waiting for a decision"
            }
            
        # Parse the instruction
        parts = instruction.lower().split()
        if not parts:
            return {
                "success": False,
                "error": "Empty instruction"
            }
            
        action_type = parts[0]
        
        if action_type == "move":
            try:
                move_index = int(parts[1])
                valid_moves = self.get_valid_moves()
                if any(move["index"] == move_index for move in valid_moves):
                    success = await self.make_move(move_index)
                    if success:
                        return {"success": True}
                return {
                    "success": False,
                    "error": "Invalid move index"
                }
            except (IndexError, ValueError):
                return {
                    "success": False,
                    "error": "Move instruction must be in format: move <index>"
                }
                
        elif action_type == "switch":
            try:
                switch_index = int(parts[1])
                valid_switches = self.get_valid_switches()
                if any(switch["index"] == switch_index for switch in valid_switches):
                    success = await self.make_switch(switch_index)
                    if success:
                        return {"success": True}
                return {
                    "success": False,
                    "error": "Invalid switch index"
                }
            except (IndexError, ValueError):
                return {
                    "success": False,
                    "error": "Switch instruction must be in format: switch <index>"
                }
                
        else:
            return {
                "success": False,
                "error": "Unknown instruction type. Use 'move <index>' or 'switch <index>'"
            }

async def main():
    """Main entry point with manual instruction testing"""
    load_dotenv()
    USERNAME = os.getenv('PS_USERNAME')
    PASSWORD = os.getenv('PS_PASSWORD')
    TARGET_USERNAME = os.getenv('PS_TARGET_USERNAME', 'blueudon')
    
    if not USERNAME or not PASSWORD:
        print("Error: Please set PS_USERNAME and PS_PASSWORD environment variables")
        sys.exit(1)
    
    print(f"Starting bot with username: {USERNAME}")
    print(f"Will challenge: {TARGET_USERNAME}")
    
    bot = ShowdownBot(USERNAME, PASSWORD, TARGET_USERNAME)
    
    # Create an input handler coroutine
    async def handle_input():
        while True:
            try:
                if bot.waiting_for_decision:
                    bot.print_available_options()
                    # Wait for user input
                    instruction = await asyncio.get_event_loop().run_in_executor(
                        None, input, "\nEnter your choice: "
                    )
                    
                    if instruction.lower() == 'quit':
                        print("Shutting down...")
                        sys.exit(0)
                    
                    # Handle the instruction
                    result = await bot.handle_instruction(instruction)
                    if not result["success"]:
                        print(f"Error: {result['error']}")
                
            except Exception as e:
                print(f"Error handling input: {str(e)}")
            
            await asyncio.sleep(0.1)  # Small delay to prevent CPU hogging
    
    # Run both the bot and input handler
    await asyncio.gather(
        bot.start(),
        handle_input()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")