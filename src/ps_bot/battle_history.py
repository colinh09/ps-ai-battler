from typing import List, Optional
import logging

class BattleHistoryTracker:
    """
    Tracks and formats Pokemon Showdown battle messages into human-readable form.
    Converts protocol messages into natural language descriptions of battle events.
    """
    
    STATUS_MAP = {
        'brn': 'burned',
        'par': 'paralyzed',
        'slp': 'put to sleep',
        'frz': 'frozen',
        'psn': 'poisoned',
        'tox': 'badly poisoned'
    }
    
    STAT_MAP = {
        'atk': 'Attack',
        'def': 'Defense',
        'spa': 'Special Attack',
        'spd': 'Special Defense',
        'spe': 'Speed',
        'accuracy': 'accuracy',
        'evasion': 'evasiveness'
    }
    
    BOOST_MAP = {
        1: 'rose',
        2: 'sharply rose',
        3: 'rose drastically',
        -1: 'fell',
        -2: 'harshly fell',
        -3: 'fell severely'
    }
    
    WEATHER_MAP = {
        'RainDance': 'It started to rain!',
        'Sandstorm': 'A sandstorm kicked up!',
        'SunnyDay': 'The sunlight turned harsh!',
        'Hail': 'It started to hail!',
        'none': 'The weather cleared up!'
    }

    def __init__(self):
        """Initialize the battle history tracker."""
        self.history: List[str] = []
        self.logger = logging.getLogger('BattleHistoryTracker')
        
    def format_pokemon_name(self, pokemon_id: str) -> str:
        """
        Convert protocol pokemon ID to readable name.
        
        Args:
            pokemon_id: Pokemon identifier from protocol (e.g., 'p1a: Pikachu')
            
        Returns:
            Formatted name with "The opposing" prefix for opponent's Pokemon
        """
        if not pokemon_id:
            return ""
            
        parts = pokemon_id.split(": ")
        if len(parts) != 2:
            return pokemon_id
            
        position, name = parts
        is_opponent = position.startswith("p2")  # Assumes p1 is the bot
        return f"The opposing {name}" if is_opponent else name

    def add_message(self, message_type: str, *args) -> None:
        """
        Format and add a battle message to history.
        
        Args:
            message_type: Type of protocol message
            *args: Message arguments from protocol
        """
        formatted = None
        
        if message_type == "move":
            pokemon, move, target = args[0], args[1], args[2] if len(args) > 2 else None
            pokemon_name = self.format_pokemon_name(pokemon)
            formatted = f"{pokemon_name} used **{move}**!"
            
        elif message_type == "-damage":
            pokemon, hp_status = args[0], args[1]
            try:
                if '/' in hp_status:
                    current, max_hp = map(float, hp_status.split('/'))
                    damage = round((1 - current/max_hp) * 100, 1)
                    formatted = f"({self.format_pokemon_name(pokemon)} lost {damage}% of its health!)"
            except:
                pass
                
        elif message_type == "-heal":
            pokemon, hp_status = args[0], args[1]
            try:
                if '/' in hp_status:
                    current, max_hp = map(float, hp_status.split('/'))
                    heal = round((current/max_hp) * 100, 1)
                    formatted = f"({self.format_pokemon_name(pokemon)} restored its HP to {heal}%!)"
            except:
                pass
                
        elif message_type == "-supereffective":
            formatted = "It's super effective!"
            
        elif message_type == "-resisted":
            formatted = "It's not very effective..."
            
        elif message_type == "-crit":
            formatted = "A critical hit!"
            
        elif message_type == "-miss":
            pokemon = args[0] if args else None
            formatted = f"The attack missed {self.format_pokemon_name(pokemon)}!" if pokemon else "The attack missed!"
            
        elif message_type == "faint":
            pokemon = args[0]
            formatted = f"{self.format_pokemon_name(pokemon)} fainted!"
            
        elif message_type == "switch":
            pokemon, details = args[0], args[1]
            formatted = f"{self.format_pokemon_name(pokemon)} was sent out!"
            
        elif message_type == "-status":
            pokemon, status = args[0], args[1]
            if status in self.STATUS_MAP:
                formatted = f"{self.format_pokemon_name(pokemon)} was {self.STATUS_MAP[status]}!"
                
        elif message_type == "-curestatus":
            pokemon, status = args[0], args[1]
            formatted = f"{self.format_pokemon_name(pokemon)}'s status was cured!"
                
        elif message_type == "-boost":
            pokemon, stat, amount = args[0], args[1], int(args[2])
            if stat in self.STAT_MAP and amount in self.BOOST_MAP:
                formatted = f"{self.format_pokemon_name(pokemon)}'s {self.STAT_MAP[stat]} {self.BOOST_MAP[amount]}!"
                
        elif message_type == "-weather":
            weather = args[0]
            if weather in self.WEATHER_MAP:
                formatted = self.WEATHER_MAP[weather]
                
        elif message_type == "-ability":
            pokemon, ability = args[0], args[1]
            formatted = f"{self.format_pokemon_name(pokemon)}'s {ability}!"
            
        elif message_type == "-item":
            pokemon, item = args[0], args[1]
            formatted = f"{self.format_pokemon_name(pokemon)} used its {item}!"
            
        elif message_type == "turn":
            formatted = f"\n=== Turn {args[0]} ===\n"
            
        elif message_type == "upkeep":
            formatted = "\n=== Upkeep Phase ===\n"

        if formatted:
            self.history.append(formatted)
            
    def get_history(self) -> str:
        """Get the complete battle history."""
        return "\n".join(self.history)
        
    def clear_history(self) -> None:
        """Clear the battle history."""
        self.history = []