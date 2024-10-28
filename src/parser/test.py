import requests
import time
import json
from collections import defaultdict
from typing import Dict, Set, List
from pprint import pprint

class ShowdownLogAnalyzer:
    def __init__(self):
        self.base_url = "https://replay.pokemonshowdown.com"
        
    def get_battle_list(self, format: str = "gen9ou", page: int = 1) -> list:
        url = f"{self.base_url}/search.json"
        response = requests.get(url, params={'format': format, 'page': page})
        return response.json()[:50]

    def get_battle_log(self, battle_id: str) -> str:
        url = f"{self.base_url}/{battle_id}.log"
        response = requests.get(url)
        return response.text

    def process_single_game(self, battle_id: str) -> List[Dict]:
        log = self.get_battle_log(battle_id)
        lines = log.split('\n')
        
        # Modified state tracking - simplified for vector DB storage
        current_state = {
            "active_pokemon": {
                "p1": {
                    "pokemon": None,
                    "hp": "100/100",
                    "status": None,
                    "ability": None,
                    "volatile_status": [],
                    "boosts": {
                        "atk": 0, "def": 0, "spa": 0, 
                        "spd": 0, "spe": 0
                    },
                    "tera_type": None
                },
                "p2": {
                    "pokemon": None,
                    "hp": "100/100",
                    "status": None,
                    "ability": None,
                    "volatile_status": [],
                    "boosts": {
                        "atk": 0, "def": 0, "spa": 0, 
                        "spd": 0, "spe": 0
                    },
                    "tera_type": None
                }
            },
            "field_conditions": {
                "weather": None,
                "terrain": None,
                "trick_room": False,
                "tailwind": {"p1": False, "p2": False}
            },
            "side_conditions": {
                "p1": {
                    "hazards": [],
                    "screens": []
                },
                "p2": {
                    "hazards": [],
                    "screens": []
                }
            },
            "remaining_pokemon": {"p1": 6, "p2": 6}
        }
        
        battle_states = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            parts = line.split('|')
            
            if len(parts) < 2:
                i += 1
                continue
                
            command = parts[1]
            
            if command == "switch" or command == "drag":
                player = parts[2][:2]
                pokemon = parts[3].split(',')[0]
                hp = parts[4]
                
                # Create state text before the switch
                pre_switch_state = self.state_to_embedding(current_state)
                
                # Update state
                current_state["active_pokemon"][player]["pokemon"] = pokemon
                current_state["active_pokemon"][player]["hp"] = hp
                current_state["active_pokemon"][player]["volatile_status"] = []
                
                # Reset boosts on switch
                for stat in current_state["active_pokemon"][player]["boosts"]:
                    current_state["active_pokemon"][player]["boosts"][stat] = 0
                
                battle_states.append({
                    "embedding_text": pre_switch_state,
                    "metadata": {
                        "type": "switch",
                        "pokemon_switched_to": pokemon,
                        "player": player,
                        "field_conditions": current_state["field_conditions"].copy(),
                        "side_conditions": current_state["side_conditions"].copy(),
                        "remaining_pokemon": current_state["remaining_pokemon"].copy()
                    }
                })
                
            elif command == "move":
                player = parts[2][:2]
                move = parts[3]
                target = "p2" if player == "p1" else "p1"
                
                # Create embedding text of current state
                current_embedding = self.state_to_embedding(current_state)
                
                # Track move outcome
                outcome = {
                    "move": move,
                    "damage": None,
                    "effects": []
                }
                
                # Look ahead for effects
                j = i + 1
                while j < len(lines):
                    effect_line = lines[j].strip()
                    effect_parts = effect_line.split('|')
                    
                    if len(effect_parts) < 2:
                        j += 1
                        continue
                    
                    effect_cmd = effect_parts[1]
                    
                    if effect_cmd in ["move", "turn", "switch", "drag"]:
                        break
                        
                    if effect_cmd == "-damage":
                        affected_player = effect_parts[2][:2]
                        old_hp = int(current_state["active_pokemon"][affected_player]["hp"].split('/')[0])
                        new_hp = effect_parts[3]
                        
                        if new_hp == "0 fnt":
                            new_hp_val = 0
                            outcome["effects"].append("faint")
                        else:
                            new_hp_val = int(new_hp.split('/')[0])
                        
                        damage = abs(new_hp_val - old_hp)
                        outcome["damage"] = damage
                        current_state["active_pokemon"][affected_player]["hp"] = new_hp
                        
                    elif effect_cmd in ["-boost", "-unboost"]:
                        affected_player = effect_parts[2][:2]
                        stat = effect_parts[3]
                        amount = int(effect_parts[4]) * (1 if effect_cmd == "-boost" else -1)
                        current_state["active_pokemon"][affected_player]["boosts"][stat] += amount
                        outcome["effects"].append(f"{'boost' if amount > 0 else 'unboost'} {stat} {abs(amount)}")
                    
                    elif effect_cmd == "-status":
                        affected_player = effect_parts[2][:2]
                        status = effect_parts[3]
                        current_state["active_pokemon"][affected_player]["status"] = status
                        outcome["effects"].append(f"status {status}")
                    
                    elif effect_cmd == "-weather":
                        weather = effect_parts[2]
                        current_state["field_conditions"]["weather"] = weather
                        outcome["effects"].append(f"weather {weather}")
                    
                    j += 1
                
                battle_states.append({
                    "embedding_text": current_embedding,
                    "metadata": {
                        "type": "move",
                        "matchup": f"{current_state['active_pokemon'][player]['pokemon']}_vs_{current_state['active_pokemon'][target]['pokemon']}",
                        "outcome": outcome,
                        "field_conditions": current_state["field_conditions"].copy(),
                        "side_conditions": current_state["side_conditions"].copy(),
                        "remaining_pokemon": current_state["remaining_pokemon"].copy()
                    }
                })
            
            elif command == "faint":
                player = parts[2][:2]
                current_state["remaining_pokemon"][player] -= 1
                current_state["active_pokemon"][player]["hp"] = "0/100"
            
            i += 1
            
        return battle_states

    def state_to_embedding(self, state: Dict) -> str:
        """Convert state to a string for vector embedding."""
        p1 = state["active_pokemon"]["p1"]
        p2 = state["active_pokemon"]["p2"]
        
        # Core matchup and state info for semantic search
        parts = [
            f"Matchup: {p1['pokemon']} vs {p2['pokemon']}",
            f"HP: {p1['pokemon']} {p1['hp']} vs {p2['pokemon']} {p2['hp']}"
        ]
        
        # Important field conditions that affect decision making
        field_conditions = []
        if state["field_conditions"]["weather"]:
            field_conditions.append(f"Weather: {state['field_conditions']['weather']}")
        if state["field_conditions"]["terrain"]:
            field_conditions.append(f"Terrain: {state['field_conditions']['terrain']}")
        if state["field_conditions"]["trick_room"]:
            field_conditions.append("Trick Room")
        if state["field_conditions"]["tailwind"]["p1"]:
            field_conditions.append("P1 Tailwind")
        if state["field_conditions"]["tailwind"]["p2"]:
            field_conditions.append("P2 Tailwind")
        
        if field_conditions:
            parts.append("Field: " + ", ".join(field_conditions))
        
        # Important boosts that affect matchup
        for player, poke in [("P1", p1), ("p2", p2)]:
            boosts = [f"{stat} {val:+d}" for stat, val in poke["boosts"].items() if val != 0]
            if boosts:
                parts.append(f"{player} boosts: {', '.join(boosts)}")
        
        # Hazards and screens
        for player in ["p1", "p2"]:
            conditions = []
            if state["side_conditions"][player]["hazards"]:
                conditions.extend(state["side_conditions"][player]["hazards"])
            if state["side_conditions"][player]["screens"]:
                conditions.extend(state["side_conditions"][player]["screens"])
            if conditions:
                parts.append(f"{player.upper()} conditions: {', '.join(conditions)}")
        
        return " | ".join(parts)

def test_single_game():
    analyzer = ShowdownLogAnalyzer()
    battle_id = "gen9ou-2232062928"
    states = analyzer.process_single_game(battle_id)
    print("\nProcessed Battle States:")
    for state in states:  # Print first two states as example
        print("\nEmbedding Text:", state["embedding_text"])
        print("Metadata:", json.dumps(state["metadata"], indent=2))

if __name__ == "__main__":
    test_single_game()