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
import logging

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
    item: Optional[str] = None
    terastallized: bool = False
    stats: Dict[str, int] = field(default_factory=lambda: {
        "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0
    })

@dataclass
class BattleState:
    active_pokemon: Dict[str, Pokemon]
    team_pokemon: Dict[str, Dict[str, Pokemon]]
    field_conditions: Dict[str, any]
    side_conditions: Dict[str, Dict[str, list]]
    tera_used: bool = False  # New field to track if tera has been used this battle
    
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
            },
            tera_used=False
        )


class ShowdownBot:
    def __init__(self, username: str, password: str, target_username: str):
        """
        Initialize the ShowdownBot with login credentials.
        
        Args:
            username (str): Pokemon Showdown username
            password (str): Pokemon Showdown password
            target_username (str): Username to interact with
        """
        self.ws = None
        self.username = username
        self.password = password
        self.target_username = target_username
        self.websocket_url = "wss://sim3.psim.us/showdown/websocket"
        self.current_battle = None
        self.battle_state = BattleState.create_initial_state()
        self.waiting_for_decision = False
        self.is_team_preview = False
        self.player_id = None
        self.current_request = None
        self.on_battle_end = None
        self.logger = logging.getLogger('ShowdownBot')
        self.challenge_status = None
        self.pending_battle_room = None
        self.battle_history = []
        self.current_turn_events = []
        self.current_turn = 0
        self.battle_concluded = False
    
    def get_opponent_id(self):
        return "p2" if self.player_id == "p1" else "p1"

    async def connect(self):
            """Connect to Pokemon Showdown websocket"""
            try:
                print(f"Connecting to {self.websocket_url}...")
                
                # Create SSL context that's more permissive
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                ssl_context.set_ciphers('DEFAULT')  # Add this line
                
                self.ws = await websockets.connect(
                    self.websocket_url,
                    ping_interval=20,        # Keep connection alive with regular pings
                    ping_timeout=60,         # Longer timeout for pings
                    close_timeout=60,        # Longer timeout before closing
                    max_size=2**23,         # Increased message size limit
                    ssl=ssl_context,
                    extra_headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Origin': 'https://play.pokemonshowdown.com',
                        'Connection': 'keep-alive',
                        'Pragma': 'no-cache',
                        'Cache-Control': 'no-cache'
                    }
                )
                print("Connected successfully!")
                return True
                
            except Exception as e:
                print(f"Failed to connect: {str(e)}")
                raise
    
    async def forfeit_battle(self) -> bool:
        """Forfeit the current battle"""
        if not self.current_battle:
            return False

        forfeit_cmd = f"{self.current_battle}|/forfeit"
        try:
            await self.ws.send(forfeit_cmd)
            print("\nForfeiting battle...")
            return True
        except Exception as e:
            print(f"Error forfeiting battle: {str(e)}")
            return False

    async def send_pm(self, user: str, message: str):
        """Send a private message to a user
        
        Args:
            user (str): Username to send message to
            message (str): Message content
        """
        try:
            MAX_LENGTH = 255
            messages = []
            current_text = ""
            
            paragraphs = message.split('\n')
            
            for paragraph in paragraphs:
                if len(paragraph.strip()) == 0:
                    continue
                    
                if len(paragraph) <= MAX_LENGTH and len(current_text) == 0:
                    messages.append(paragraph)
                    continue
                    
                sentences = re.split(r'([.!?]+(?:\s+|$))', paragraph)
                
                complete_sentences = []
                for i in range(0, len(sentences)-1, 2):
                    if i+1 < len(sentences):
                        complete_sentences.append(sentences[i] + sentences[i+1])
                if len(sentences) % 2 == 1:
                    complete_sentences.append(sentences[-1])
                
                for sentence in complete_sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                        
                    if len(current_text + " " + sentence if current_text else sentence) > MAX_LENGTH:
                        if current_text:
                            messages.append(current_text.strip())
                        current_text = sentence
                    else:
                        current_text = (current_text + " " + sentence if current_text else sentence)
                
            if current_text:
                messages.append(current_text.strip())
                
            for msg in messages:
                if msg.strip():
                    pm_command = f"|/pm {user}, {msg.strip()}"
                    print(f"Sending PM: {pm_command}")
                    await self.ws.send(pm_command)
                    await asyncio.sleep(0.3)
                    
        except Exception as e:
            print(f"Error sending PM: {str(e)}")

    async def send_battle_message(self, message: str) -> None:
        """Send a message to the current battle room chat.
        
        Args:
            message (str): The message to send to the battle room
        """
        if not self.current_battle:
            return
            
        try:
            MAX_LENGTH = 255
            messages = []
            current_text = ""
            
            # First split by newlines to preserve intentional line breaks
            paragraphs = message.split('\n')
            
            for paragraph in paragraphs:
                if len(paragraph.strip()) == 0:
                    continue
                    
                # If paragraph fits entirely within limit, and current_text is empty
                if len(paragraph) <= MAX_LENGTH and len(current_text) == 0:
                    messages.append(paragraph)
                    continue
                    
                # Split paragraph into sentences
                # Handle multiple sentence endings (.!?)
                sentences = re.split(r'([.!?]+(?:\s+|$))', paragraph)
                
                # Recombine sentences with their punctuation
                complete_sentences = []
                for i in range(0, len(sentences)-1, 2):
                    if i+1 < len(sentences):
                        complete_sentences.append(sentences[i] + sentences[i+1])
                if len(sentences) % 2 == 1:
                    complete_sentences.append(sentences[-1])
                
                for sentence in complete_sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                        
                    # If adding this sentence would exceed limit
                    if len(current_text + " " + sentence if current_text else sentence) > MAX_LENGTH:
                        # Save current text if we have any
                        if current_text:
                            messages.append(current_text.strip())
                        current_text = sentence
                    else:
                        # Add to current text with space if needed
                        current_text = (current_text + " " + sentence if current_text else sentence)
                
            # Add any remaining text
            if current_text:
                messages.append(current_text.strip())
                
            # Send all messages with a small delay between them
            for msg in messages:
                if msg.strip():  # Only send non-empty messages
                    formatted_message = f"{self.current_battle}|{msg.strip()}"
                    print(f"Sending battle message: {formatted_message}")  # Debug print
                    await self.ws.send(formatted_message)
                    await asyncio.sleep(0.3)  # Small delay between messages
                    
        except Exception as e:
            print(f"Error sending battle message: {str(e)}")

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


    async def make_move(self, move_index: int, tera: bool = False) -> bool:
        """
        Try to make a move with the given index
        
        Args:
            move_index (int): Index of the move to use
            tera (bool): Whether to terastallize before using the move
        """
        if not self.current_battle or not self.waiting_for_decision:
            return False
        
        # Build the move command
        if tera:
            move_cmd = f"{self.current_battle}|/choose move {move_index} terastallize"
            # Set the tera flags when we use it
            self.battle_state.tera_used = True
            if self.battle_state.active_pokemon[self.player_id]:
                self.battle_state.active_pokemon[self.player_id].terastallized = True
        else:
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

    def format_pokemon_name(self, pokemon_id: str) -> str:
        """Format a Pokemon ID into a readable name with ownership."""
        if not pokemon_id:
            return "Unknown Pokemon"
        
        parts = pokemon_id.split(': ')
        if len(parts) != 2:
            return pokemon_id
            
        player, name = parts
        is_opponent = (player == "p1" and self.player_id == "p2") or (player == "p2" and self.player_id == "p1")
        return f"The opposing {name}" if is_opponent else name

    def add_battle_event(self, event: str):
        """Add an event to the current turn's history."""
        self.current_turn_events.append(event)

    async def handle_battle_message(self, room_id: str, message: str):
        """Handle messages from a battle room"""
        try:
            if "|init|battle" in message:
                self.current_battle = room_id.strip('>')
                self.battle_state = BattleState.create_initial_state()
                self.battle_history = []  # Reset battle history for new battle
                self.current_turn_events = []
                self.current_turn = 0
                self.battle_concluded = False 
                print(f"Joined battle room: {self.current_battle}")
                await self.ws.send(f"|/join {self.current_battle}")
            
            for line in message.split('\n'):
                parts = line.strip().split('|')
                if len(parts) < 2:
                    continue
                    
                command = parts[1]
                
                print(f"Processing command: {command}")
                if len(parts) > 2:
                    print(f"Command data: {parts[2:]}")
                
                # Track turn numbers
                if command == "turn":
                    if self.current_turn_events:
                        self.battle_history.append({
                            'turn': self.current_turn,
                            'events': self.current_turn_events.copy()
                        })
                    self.current_turn = int(parts[2])
                    self.current_turn_events = [f"Turn {self.current_turn}:"]
                
                # Track major battle events
                elif command == "move":
                    pokemon = self.format_pokemon_name(parts[2])
                    move = parts[3]
                    self.add_battle_event(f"{pokemon} used {move}!")
                    
                    # Update battle state for moves
                    player = parts[2][:2]
                    move = parts[3]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].moves.add(move)
                
                elif command == "switch" or command == "drag":
                    pokemon = self.format_pokemon_name(parts[2])
                    switched_to = parts[3].split(',')[0]
                    self.add_battle_event(f"{pokemon} switched to {switched_to}!")
                    
                    # Update battle state for switches
                    player = parts[2][:2]
                    await self.handle_switch(player, parts[3], parts[4])
                
                elif command == "-damage":
                    pokemon = self.format_pokemon_name(parts[2])
                    # Calculate damage percentage
                    try:
                        current_hp, max_hp = parts[3].split('/')
                        if max_hp.endswith(')'):  # Remove status condition if present
                            max_hp = max_hp.split()[0]
                        current_hp = float(current_hp)
                        max_hp = float(max_hp)
                        damage_percent = round((1 - current_hp/max_hp) * 100, 1)
                        self.add_battle_event(f"{pokemon} lost {damage_percent}% of its health!")
                    except (ValueError, IndexError):
                        self.add_battle_event(f"{pokemon} took damage!")
                        
                    # Update battle state for damage
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].hp = parts[3].split()[0]
                        if len(parts[3].split()) > 1:
                            self.battle_state.active_pokemon[player].status = parts[3].split()[1]
                
                elif command == "-heal":
                    pokemon = self.format_pokemon_name(parts[2])
                    try:
                        current_hp, max_hp = parts[3].split('/')
                        if max_hp.endswith(')'):
                            max_hp = max_hp.split()[0]
                        current_hp = float(current_hp)
                        max_hp = float(max_hp)
                        heal_percent = round((current_hp/max_hp) * 100, 1)
                        self.add_battle_event(f"{pokemon} restored health! ({heal_percent}% remaining)")
                    except (ValueError, IndexError):
                        self.add_battle_event(f"{pokemon} restored health!")
                
                elif command == "-supereffective":
                    self.add_battle_event("It's super effective!")
                
                elif command == "-resisted":
                    self.add_battle_event("It's not very effective...")
                
                elif command == "-crit":
                    self.add_battle_event("A critical hit!")
                
                elif command == "-status":
                    pokemon = self.format_pokemon_name(parts[2])
                    status = parts[3]
                    status_map = {
                        'brn': 'burned',
                        'par': 'paralyzed',
                        'psn': 'poisoned',
                        'tox': 'badly poisoned',
                        'frz': 'frozen',
                        'slp': 'put to sleep'
                    }
                    status_text = status_map.get(status, status)
                    self.add_battle_event(f"{pokemon} was {status_text}!")
                    
                    # Update battle state for status
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].status = parts[3]
                
                elif command == "faint":
                    pokemon = self.format_pokemon_name(parts[2])
                    self.add_battle_event(f"{pokemon} fainted!")
                    
                    # Update battle state for faint
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        print(f"Setting HP to 0 for {self.battle_state.active_pokemon[player].name}")
                        self.battle_state.active_pokemon[player].hp = "0/100"
                        # Also update the team Pokemon's HP
                        active_name = self.battle_state.active_pokemon[player].name
                        if active_name in self.battle_state.team_pokemon[player]:
                            self.battle_state.team_pokemon[player][active_name].hp = "0/100"
                
                elif command == "-boost":
                    pokemon = self.format_pokemon_name(parts[2])
                    stat = parts[3]
                    stat_map = {
                        'atk': 'Attack',
                        'def': 'Defense',
                        'spa': 'Special Attack',
                        'spd': 'Special Defense',
                        'spe': 'Speed',
                        'accuracy': 'accuracy',
                        'evasion': 'evasiveness'
                    }
                    stat_name = stat_map.get(stat, stat)
                    self.add_battle_event(f"{pokemon}'s {stat_name} rose!")
                    
                    # Update battle state for boosts
                    player = parts[2][:2]
                    amount = int(parts[4])
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].boosts[stat] += amount
                
                elif command == "-unboost":
                    pokemon = self.format_pokemon_name(parts[2])
                    stat = parts[3]
                    stat_map = {
                        'atk': 'Attack',
                        'def': 'Defense',
                        'spa': 'Special Attack',
                        'spd': 'Special Defense',
                        'spe': 'Speed',
                        'accuracy': 'accuracy',
                        'evasion': 'evasiveness'
                    }
                    stat_name = stat_map.get(stat, stat)
                    self.add_battle_event(f"{pokemon}'s {stat_name} fell!")
                    
                    # Update battle state for unboosts
                    player = parts[2][:2]
                    amount = -int(parts[4])
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].boosts[stat] += amount
                
                elif command == "-weather":
                    weather = parts[2]
                    weather_map = {
                        'RainDance': 'Rain started falling!',
                        'Sandstorm': 'A sandstorm kicked up!',
                        'SunnyDay': 'The sunlight turned harsh!',
                        'Hail': 'It started to hail!',
                        'none': 'The weather cleared up!'
                    }
                    weather_text = weather_map.get(weather, f"The weather became {weather}!")
                    self.add_battle_event(weather_text)
                    
                    # Update battle state for weather
                    weather = parts[2] if parts[2] != "none" else None
                    self.battle_state.field_conditions["weather"] = weather
                
                elif command == "player":
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
                
                elif command == "-ability":
                    player = parts[2][:2]
                    if player in self.battle_state.active_pokemon and self.battle_state.active_pokemon[player]:
                        self.battle_state.active_pokemon[player].ability = parts[3]
                        
                        # Also update the team Pokemon's ability
                        active_name = self.battle_state.active_pokemon[player].name
                        if active_name in self.battle_state.team_pokemon[player]:
                            self.battle_state.team_pokemon[player][active_name].ability = parts[3]
                
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
                    
                    if any(hazard in condition.lower() for hazard in ["spikes", "stealth rock", "toxic spikes", "sticky web"]):
                        self.battle_state.side_conditions[player]["hazards"].append(condition)
                    elif any(screen in condition.lower() for screen in ["reflect", "light screen", "aurora veil"]):
                        self.battle_state.side_conditions[player]["screens"].append(condition)
                    
                elif command == "-sideend":
                    player = parts[2][:2]
                    condition = parts[3]
                    
                    if any(hazard in condition.lower() for hazard in ["spikes", "stealth rock", "toxic spikes", "sticky web"]):
                        if condition in self.battle_state.side_conditions[player]["hazards"]:
                            self.battle_state.side_conditions[player]["hazards"].remove(condition)
                    elif any(screen in condition.lower() for screen in ["reflect", "light screen", "aurora veil"]):
                        if condition in self.battle_state.side_conditions[player]["screens"]:
                            self.battle_state.side_conditions[player]["screens"].remove(condition)
                
                elif command == "win" or (command == "-message" and len(parts) > 2 and "forfeited" in parts[2].lower()):
                    # Avoid duplicate processing
                    self.battle_concluded = True
                    if not self.current_battle:
                        return
                        
                    # Save the final turn's events
                    if self.current_turn_events:
                        self.battle_history.append({
                            'turn': self.current_turn,
                            'events': self.current_turn_events.copy()
                        })
                    
                    # Capture final state and history BEFORE clearing anything
                    final_state = self.get_game_state()
                    final_history = self.get_battle_history_text()
                    
                    self.logger.info("Battle has concluded")
                    
                    # Clear battle data before analysis to prevent duplicate triggers
                    current_battle = self.current_battle
                    self.current_battle = None
                    self.waiting_for_decision = False
                    
                    # Call battle_end handler with final data
                    if self.on_battle_end:
                        await self.on_battle_end(final_state, final_history)
                    
                    return
                    
                elif command == "request":
                    if not parts[2]:
                        continue
                    
                    request = json.loads(parts[2])
                    self.current_request = request
                    
                    if "side" in request:
                        for pokemon_data in request["side"]["pokemon"]:
                            name = pokemon_data["ident"].split(": ")[1]
                            if name not in self.battle_state.team_pokemon[self.player_id]:
                                self.battle_state.team_pokemon[self.player_id][name] = Pokemon(name=name)
                            
                            pokemon = self.battle_state.team_pokemon[self.player_id][name]
                            
                            # Update item
                            pokemon.item = pokemon_data.get("item")
                            
                            # Update HP condition
                            pokemon.hp = pokemon_data.get("condition", "100/100")
                            
                            # Update stats
                            if "stats" in pokemon_data:
                                pokemon.stats = pokemon_data["stats"]
                            
                            # Update ability - prioritize current ability over base ability
                            new_ability = pokemon_data.get("ability") or pokemon_data.get("baseAbility")
                            if new_ability:
                                pokemon.ability = new_ability
                            
                            # Update Tera type and status
                            pokemon.tera_type = pokemon_data.get("teraType")
                            pokemon.terastallized = bool(pokemon_data.get("terastallized"))
                            
                            # Update moves - merge with existing moves 
                            if "moves" in pokemon_data:
                                # For active Pokemon, replace the complete moveset
                                if pokemon_data.get("active"):
                                    pokemon.moves = set(move for move in pokemon_data["moves"])
                                else:
                                    # For inactive Pokemon, add to existing moves
                                    pokemon.moves.update(move for move in pokemon_data["moves"])
                            
                            # If this is the active Pokemon, update it in active_pokemon
                            if pokemon_data.get("active"):
                                self.battle_state.active_pokemon[self.player_id] = pokemon
                    
                    # Additional handling for active Pokemon's available moves
                    if "active" in request and request["active"] and len(request["active"]) > 0:
                        try:
                            active_data = request["active"][0]
                            active_pokemon = self.battle_state.active_pokemon[self.player_id]
                            
                            # Update moves for active Pokemon from the moves array
                            if active_pokemon and "moves" in active_data:
                                # Create a set of all available moves
                                available_moves = set()
                                for move in active_data["moves"]:
                                    if isinstance(move, dict) and "move" in move:
                                        available_moves.add(move["move"])
                                    elif isinstance(move, str):
                                        available_moves.add(move)
                                
                                # Update the Pokemon's moves
                                active_pokemon.moves.update(available_moves)
                                
                                # Also update the team Pokemon's moves
                                if active_pokemon.name in self.battle_state.team_pokemon[self.player_id]:
                                    self.battle_state.team_pokemon[self.player_id][active_pokemon.name].moves.update(available_moves)
                                
                        except IndexError:
                            print("WARNING: Could not access active[0] - active list is empty")
                        except Exception as e:
                            print(f"ERROR processing active Pokemon: {str(e)}")
                    
                    await asyncio.sleep(0.1)
                    
                    if "forceSwitch" in request and request["forceSwitch"][0]:
                        self.waiting_for_decision = True
                        
                    elif "active" in request and request["active"] and len(request["active"]) > 0:
                        self.waiting_for_decision = True
                
                elif command == "error":
                    self.waiting_for_decision = True
        
        except Exception as e:
            print(f"Error in handle_battle_message: {str(e)}")
            print(f"Message was: {message}")
            print("Full error details:", str(e.__class__.__name__), str(e))
            import traceback
            print("Traceback:", traceback.format_exc())

    def get_battle_history_text(self) -> str:
        """Get a formatted string of the battle history."""
        history_text = []
        for turn in self.battle_history:
            history_text.extend(turn['events'])
        if self.current_turn_events:  # Add current turn's events
            history_text.extend(self.current_turn_events)
        return '\n'.join(history_text)

    async def handle_battle_end(self, winner: Optional[str] = None):
        """Handle end of battle and store final state"""
        # Save the final turn's events before ending
        if self.current_turn_events:
            self.battle_history.append({
                'turn': self.current_turn,
                'events': self.current_turn_events.copy()
            })
        
        # Store the winner if provided
        self.battle_winner = winner
        
        # Store final battle state
        self.final_battle_state = self.get_game_state()
        
        self.logger.info("Battle has concluded")
        self.current_battle = None
        self.waiting_for_decision = False
        if self.on_battle_end:
            await self.on_battle_end()

    async def receive_messages(self):
        try:
            initial_challenge_sent = False 
            while True:
                if self.battle_concluded:
                    break
                message = await self.ws.recv()
                
                if "|challstr|" in message:
                    challstr = message.split("|challstr|")[1]
                    await self.login(challstr, False)
                    await asyncio.sleep(2)
                    # Only send challenge the first time
                    if not initial_challenge_sent:
                        await self.ws.send("|/utm null")
                        await self.ws.send(f"|/challenge {self.target_username}, gen9randombattle")
                        initial_challenge_sent = True
                
                elif "|updatechallenges|" in message:
                    data = json.loads(message.split("|updatechallenges|")[1])
                    # If there's a game, that means challenge was accepted
                    if data.get('games'):
                        room_id = next(iter(data['games']))
                        print(f"Challenge accepted! Battle room: {room_id}")
                        self.current_battle = room_id
                
                elif message.startswith(">battle-"):
                    room_id = message.split("\n")[0]
                    if "|init|battle" in message and room_id.strip('>') == self.current_battle:
                        print(f"Joining battle room: {self.current_battle}")
                        await self.ws.send(f"|/join {self.current_battle}")
                    await self.handle_battle_message(room_id, message)

        except websockets.exceptions.ConnectionClosed:
            print("Connection closed unexpectedly")
            raise
        except Exception as e:
            print(f"Error in receive_messages: {str(e)}")
            raise

    async def challenge_player(self, username: str):
        """Send a Random Battle challenge to a specific player
        
        Args:
            username (str): Player to challenge
        """
        try:
            print(f"Challenging {username} to a Random Battle...")
            # For Random Battle, we don't need a team
            await self.ws.send("|/utm null")
            await self.ws.send(f"|/challenge {username}, gen9randombattle")
        except Exception as e:
            print(f"Error sending challenge: {str(e)}")
            raise

    async def login(self, challstr, first_msg):
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
            
            # Send initial greeting after successful login
            if first_msg:
                greeting = "Hi! I'm your Pokemon battle companion. I can help you with Pokemon battles and discuss strategies. You can ask me to start a battle, or we can chat about Pokemon strategies. What would you like to do?"
                await self.send_pm(self.target_username, greeting)
            
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
        active_pokemon = self.battle_state.active_pokemon[self.player_id]
        # Can tera if we haven't used it this battle and current Pokemon isn't already terastallized 
        can_tera = (not self.battle_state.tera_used and 
                    active_pokemon and 
                    not active_pokemon.terastallized)
        
        # Only include non-disabled moves
        for i, move in enumerate(active["moves"], 1):
            if not move.get("disabled", False):  # Explicitly check disabled flag
                move_data = {
                    "index": i,
                    "move": move["move"],
                    "type": move.get("type"),
                    "pp": move.get("pp", 0),
                    "maxpp": move.get("maxpp", 0),
                    "can_tera": can_tera 
                }
                valid_moves.append(move_data)
        return valid_moves

    def get_valid_switches(self) -> List[Dict]:
        """Get list of valid switches from current request"""
        if not self.current_request or "side" not in self.current_request:
            return []
            
        valid_switches = []
        for i, pokemon in enumerate(self.current_request["side"]["pokemon"], 1):
            # Check for actively battling Pokemon - can't switch to active Pokemon
            if pokemon.get("active", False):
                continue
                
            # Parse the condition to check for fainted status
            condition = pokemon.get("condition", "")
            is_fainted = (
                pokemon.get("fainted", False) or  # Check explicit fainted flag
                condition == "0 fnt" or           # Check string condition
                condition == "0" or               # Check just 0 HP
                "/0" in condition or             # Check ratio with 0 HP
                "fnt" in condition               # Check for faint in condition
            )
            
            if not is_fainted:
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
            "valid_switches": self.get_valid_switches(),
            "tera_used": self.battle_state.tera_used
        }
        
        # Add active Pokemon info
        if self.battle_state.active_pokemon[self.player_id]:
            pokemon = self.battle_state.active_pokemon[self.player_id]
            state["active"]["self"] = {
                "name": pokemon.name,
                "hp": pokemon.hp,
                "status": pokemon.status,
                "ability": pokemon.ability,
                "moves": list(pokemon.moves),
                "boosts": pokemon.boosts,
                "volatile_status": pokemon.volatile_status,
                "item": pokemon.item,
                "tera_type": pokemon.tera_type,
                "terastallized": pokemon.terastallized,
                "stats": pokemon.stats
            }
            
        if self.battle_state.active_pokemon[self.get_opponent_id()]:
            pokemon = self.battle_state.active_pokemon[self.get_opponent_id()]
            state["active"]["opponent"] = {
                "name": pokemon.name,
                "hp": pokemon.hp,
                "status": pokemon.status,
                "ability": pokemon.ability,
                "moves": list(pokemon.moves),
                "boosts": pokemon.boosts,
                "volatile_status": pokemon.volatile_status,
                "item": pokemon.item,
                "tera_type": pokemon.tera_type,
                "terastallized": pokemon.terastallized,
                "stats": pokemon.stats
            }
            
        # Add team Pokemon info
        for name, pokemon in self.battle_state.team_pokemon[self.player_id].items():
            state["team"]["self"][name] = {
                "hp": pokemon.hp,
                "status": pokemon.status,
                "ability": pokemon.ability,
                "moves": list(pokemon.moves),
                "item": pokemon.item,
                "tera_type": pokemon.tera_type,
                "terastallized": pokemon.terastallized,
                "stats": pokemon.stats
            }
            
        for name, pokemon in self.battle_state.team_pokemon[self.get_opponent_id()].items():
            if pokemon.revealed:  # Only include revealed opponent Pokemon
                state["team"]["opponent"][name] = {
                    "hp": pokemon.hp,
                    "status": pokemon.status,
                    "ability": pokemon.ability,
                    "moves": list(pokemon.moves),
                    "item": pokemon.item,
                    "tera_type": pokemon.tera_type,
                    "terastallized": pokemon.terastallized,
                    "stats": pokemon.stats
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
                # Check if it's a terastallize move
                move_str = parts[1]
                tera = move_str.endswith('t')
                
                # Remove 't' if present and convert to integer
                move_index = int(move_str.rstrip('t'))
                
                valid_moves = self.get_valid_moves()
                if any(move["index"] == move_index for move in valid_moves):
                    # If trying to terastallize, verify it's allowed
                    active_pokemon = self.battle_state.active_pokemon[self.player_id]
                    if tera:
                        if active_pokemon and active_pokemon.terastallized:
                            return {
                                "success": False,
                                "error": "Pokemon is already terastallized"
                            }
                        if self.battle_state.tera_used:
                            return {
                                "success": False,
                                "error": "Already used terastallize this battle"
                            }
                            
                    success = await self.make_move(move_index, tera)
                    if success:
                        return {"success": True}
                return {
                    "success": False,
                    "error": "Invalid move index"
                }
            except (IndexError, ValueError):
                return {
                    "success": False,
                    "error": "Move instruction must be in format: move <index> or move <index>t for terastallize"
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
                "error": "Unknown instruction type. Use 'move <index>', 'move <index>t' for terastallize, or 'switch <index>'"
            }