import os
import logging
import json
from typing import Dict, Any, List, Optional, Set
from dotenv import load_dotenv
from .model_wrappers.api_gateway import APIGateway
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PSAgent')

import psycopg2
from psycopg2.extras import RealDictCursor
import json
from typing import Dict, Any, List, Optional, Set
import logging

class PokemonDBTools:
    def __init__(self, db_params: Dict[str, str]):
        """Initialize database connection"""
        self.db_params = db_params
        self.logger = logging.getLogger('PSAgent.DBTools')
        
    def get_connection(self):
        """Create and return a database connection"""
        self.logger.debug(f"Attempting to connect to database: {self.db_params['dbname']} at {self.db_params['host']}")
        return psycopg2.connect(**self.db_params)

    def merge_random_battle_sets(self, sets: List[Dict]) -> Dict:
        """
        Merge multiple random battle sets into a single combined set.
        
        Args:
            sets: List of random battle set dictionaries from the database
            
        Returns:
            Dict containing merged unique values for each field
        """
        if not sets:
            return {}
            
        # Initialize merged set with first set's values
        merged = {
            'pokemon_name': sets[0]['pokemon_name'],
            'level': sets[0]['level'],  # All sets should have same level
            'roles': set([sets[0]['role_name']]),  # Track all possible roles
            'abilities': set(),
            'items': set(),
            'tera_types': set(),
            'moves': set(),
            'evs': sets[0]['evs'],  # Keep first set's EVs if they exist
            'ivs': sets[0]['ivs']   # Keep first set's IVs if they exist
        }
        
        # Process first set's JSONB data (already Python lists from psycopg2)
        merged['abilities'].update(sets[0]['abilities'])
        merged['items'].update(sets[0]['items'])
        merged['tera_types'].update(sets[0]['tera_types'])
        merged['moves'].update(sets[0]['moves'])
        
        # Merge remaining sets
        for set_data in sets[1:]:
            merged['roles'].add(set_data['role_name'])
            merged['abilities'].update(set_data['abilities'])
            merged['items'].update(set_data['items'])
            merged['tera_types'].update(set_data['tera_types'])
            merged['moves'].update(set_data['moves'])
            
            # If current set has EVs/IVs and merged doesn't, use these
            if not merged['evs'] and set_data['evs']:
                merged['evs'] = set_data['evs']
            if not merged['ivs'] and set_data['ivs']:
                merged['ivs'] = set_data['ivs']
        
        # Convert sets back to sorted lists for consistency
        merged['abilities'] = sorted(list(merged['abilities']))
        merged['items'] = sorted(list(merged['items']))
        merged['tera_types'] = sorted(list(merged['tera_types']))
        merged['moves'] = sorted(list(merged['moves']))
        merged['roles'] = sorted(list(merged['roles']))
        
        return merged

    def get_best_random_battle_set(
        self, 
        pokemon_name: str, 
        known_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get the best matching random battle set for a Pokemon.
        For opponent Pokemon (known_data=None), merges all possible sets.
        For agent Pokemon, finds best matching set based on known data.
        
        Args:
            pokemon_name: Name of the Pokemon
            known_data: Dict containing known ability, item, and moves (for agent's Pokemon)
            
        Returns:
            Dict containing the best matching or merged set data
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all sets for this Pokemon
                cur.execute("""
                    SELECT * FROM random_battle_sets 
                    WHERE pokemon_name = %s
                """, (pokemon_name,))
                sets = cur.fetchall()
                
                if not sets:
                    return {}
                
                # For opponent Pokemon or if no known data, merge all sets
                if not known_data:
                    return self.merge_random_battle_sets(sets)
                
                # For agent Pokemon, find best matching set
                matching_sets = []
                
                for set_data in sets:
                    matches = True
                    
                    # Check ability match if known
                    if known_data.get('ability'):
                        if known_data['ability'] not in set_data['abilities']:
                            continue
                    
                    # Check item match if known
                    if known_data.get('item'):
                        if known_data['item'] not in set_data['items']:
                            continue
                    
                    # Check if known moves are subset of possible moves
                    if known_data.get('moves'):
                        if not set(known_data['moves']).issubset(set(set_data['moves'])):
                            continue
                    
                    matching_sets.append(set_data)
                
                # If we found matching sets, merge them
                if matching_sets:
                    return self.merge_random_battle_sets(matching_sets)
                
                # If no matches found, merge all sets as fallback
                return self.merge_random_battle_sets(sets)

    def calculate_type_matchups(self, type1: str, type2: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        """
        Calculate both offensive and defensive type matchups for a Pokemon
        
        Returns:
            Dict with both 'attacking' and 'defending' matchups
        """
        self.logger.info(f"Calculating type matchups for type1={type1}, type2={type2}")
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Calculate defensive matchups (what's super effective against us)
                self.logger.debug("Calculating defensive matchups")
                cur.execute("""
                    SELECT attacking_type, multiplier 
                    FROM types_defending 
                    WHERE defending_type = %s
                """, (type1,))
                
                defensive_matchups = {row['attacking_type']: float(row['multiplier']) 
                                    for row in cur.fetchall()}
                
                # If this is a dual-type Pokemon, factor in the second type's defensive matchups
                if type2:
                    cur.execute("""
                        SELECT attacking_type, multiplier 
                        FROM types_defending 
                        WHERE defending_type = %s
                    """, (type2,))
                    
                    type2_defensive = {row['attacking_type']: float(row['multiplier']) 
                                    for row in cur.fetchall()}
                    
                    # Combine matchups by multiplying effectiveness
                    for attack_type, multiplier in type2_defensive.items():
                        if attack_type in defensive_matchups:
                            defensive_matchups[attack_type] *= multiplier
                        else:
                            defensive_matchups[attack_type] = multiplier
                
                # Calculate offensive matchups (what we're super effective against)
                self.logger.debug("Calculating offensive matchups")
                cur.execute("""
                    SELECT defending_type, multiplier 
                    FROM types_attacking 
                    WHERE attacking_type = %s
                """, (type1,))
                
                offensive_matchups = {row['defending_type']: float(row['multiplier']) 
                                    for row in cur.fetchall()}
                
                # If dual-type, get the second type's offensive matchups
                if type2:
                    cur.execute("""
                        SELECT defending_type, multiplier 
                        FROM types_attacking 
                        WHERE attacking_type = %s
                    """, (type2,))
                    
                    type2_offensive = {row['defending_type']: float(row['multiplier']) 
                                    for row in cur.fetchall()}
                    
                    # For offensive matchups, take the best multiplier
                    for defend_type, multiplier in type2_offensive.items():
                        if defend_type in offensive_matchups:
                            offensive_matchups[defend_type] = max(
                                offensive_matchups[defend_type], 
                                multiplier
                            )
                        else:
                            offensive_matchups[defend_type] = multiplier
                
                self.logger.debug(f"Defensive matchups: {defensive_matchups}")
                self.logger.debug(f"Offensive matchups: {offensive_matchups}")
                
                return {
                    'defending': defensive_matchups,
                    'attacking': offensive_matchups
                }

    def get_pokemon_complete_data(self, pokemon_name: str, known_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get complete information about a Pokemon including random battle set data.
        For agent's Pokemon with known_data, uses keys to look up associated data.
        For opponent Pokemon, uses regular names.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First get the random battle set data
                random_battle_data = self.get_best_random_battle_set(pokemon_name, known_data)
                
                # Get Pokemon data - for agent Pokemon, try by key first
                if known_data:
                    pokemon_key = pokemon_name.lower().replace(' ', '')
                    cur.execute("""
                        SELECT * FROM pokemon WHERE key = %s
                    """, (pokemon_key,))
                    pokemon_data = cur.fetchone()
                    
                    if not pokemon_data:
                        # Fallback to name lookup
                        cur.execute("""
                            SELECT * FROM pokemon WHERE pokemon_name = %s
                        """, (pokemon_name,))
                        pokemon_data = cur.fetchone()
                else:
                    # For opponent Pokemon, lookup by name directly
                    cur.execute("""
                        SELECT * FROM pokemon WHERE pokemon_name = %s
                    """, (pokemon_name,))
                    pokemon_data = cur.fetchone()
                
                if not pokemon_data:
                    self.logger.error(f"Pokemon not found: {pokemon_name}")
                    return {"error": f"Pokemon {pokemon_name} not found"}
                
                self.logger.debug(f"Found Pokemon data: {pokemon_data}")
                result = dict(pokemon_data)
                
                # Add the known_data flag to differentiate own vs opponent Pokemon
                if known_data:
                    result['known_data'] = known_data
                
                # Get ability descriptions
                abilities = []
                for ability_key in ['ability1', 'ability2', 'ability3']:
                    if result[ability_key]:
                        self.logger.debug(f"Fetching ability data for: {result[ability_key]}")
                        ability_data = self.get_ability_data(result[ability_key])
                        if ability_data:
                            abilities.append({
                                'name': ability_data['ability_name'],
                                'description': ability_data['description']
                            })
                        else:
                            self.logger.warning(f"No ability data found for: {result[ability_key]}")
                
                result['abilities'] = abilities
                
                # Calculate type matchups
                self.logger.debug("Calculating type matchups")
                result['type_matchups'] = self.calculate_type_matchups(
                    result['type1'],
                    result['type2']
                )
                
                # Add random battle set data
                result['random_battle_data'] = random_battle_data
                return result
    
    def get_move_data(self, move_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete data for a move from the database.
        For agent's Pokemon, uses the key (lowercase no spaces) to look up moves.
        For opponent Pokemon, uses the regular move name.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try lookup by key first (for agent's Pokemon)
                move_key = move_name.lower().replace(' ', '')
                cur.execute("""
                    SELECT * FROM moves WHERE key = %s
                """, (move_key,))
                move_data = cur.fetchone()
                
                if not move_data:
                    # If not found by key, try by name (for opponent Pokemon)
                    cur.execute("""
                        SELECT * FROM moves WHERE move_name = %s
                    """, (move_name,))
                    move_data = cur.fetchone()
                
                return dict(move_data) if move_data else None

    def get_ability_data(self, ability_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete data for an ability from the database.
        For agent's Pokemon, uses the key (lowercase no spaces) to look up abilities.
        For opponent Pokemon, uses the regular ability name.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try lookup by key first (for agent's Pokemon)
                ability_key = ability_name.lower().replace(' ', '')
                cur.execute("""
                    SELECT * FROM abilities WHERE key = %s
                """, (ability_key,))
                ability_data = cur.fetchone()
                
                if not ability_data:
                    # If not found by key, try by name (for opponent Pokemon)
                    cur.execute("""
                        SELECT * FROM abilities WHERE ability_name = %s
                    """, (ability_name,))
                    ability_data = cur.fetchone()
                
                return dict(ability_data) if ability_data else None

    def get_item_data(self, item_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete data for an item from the database.
        For agent's Pokemon, uses the key (lowercase no spaces) to look up items.
        For opponent Pokemon, uses the regular item name.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try lookup by key first (for agent's Pokemon)
                item_key = item_name.lower().replace(' ', '')
                cur.execute("""
                    SELECT * FROM items WHERE key = %s
                """, (item_key,))
                item_data = cur.fetchone()
                
                if not item_data:
                    # If not found by key, try by name (for opponent Pokemon)
                    cur.execute("""
                        SELECT * FROM items WHERE item_name = %s
                    """, (item_name,))
                    item_data = cur.fetchone()
                
                return dict(item_data) if item_data else None
    

class PSAgent:
    def __init__(self, api_key: Optional[str] = None, db_params: Dict[str, str] = None):
        """
        Initialize the Pokemon Showdown agent with database support
        """
        self.logger = logging.getLogger('PSAgent.Main')
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv("SAMBANOVA_API_KEY")
        if not self.api_key:
            self.logger.error("No API key provided")
            raise ValueError("SAMBANOVA_API_KEY must be set in .env file or passed to constructor")
        
        # Initialize the LLM
        self.logger.info("Initializing LLM")
        self.llm = self._init_llm()
        
        # Initialize DB tools
        self.logger.info("Initializing DB tools")
        self.db_tools = PokemonDBTools(db_params)
    
    def _init_llm(self):
        """Initialize the SambaNova LLM"""
        self.logger.debug("Creating LLM instance")
        return APIGateway.load_llm(
            type="sncloud",
            temperature=0.7,
            max_tokens_to_generate=1024,
            select_expert="llama3-70b",
            coe=True,
            do_sample=False,
            sambanova_api_key=self.api_key
        )
    
    def format_pokemon_data(self, pokemon_data: Dict[str, Any]) -> str:
        """Format Pokemon data for the LLM with set role for own Pokemon and all possibilities for opponent"""
        self.logger.info("Formatting Pokemon data for LLM")
        
        if "error" in pokemon_data:
            self.logger.error(f"Error in Pokemon data: {pokemon_data['error']}")
            return pokemon_data["error"]
        
        # Format defensive matchups
        weaknesses = []
        resistances = []
        immunities = []
        
        for type_name, multiplier in pokemon_data['type_matchups']['defending'].items():
            if multiplier > 1:
                weaknesses.append(f"{type_name} ({multiplier}x)")
            elif multiplier < 1 and multiplier > 0:
                resistances.append(f"{type_name} ({multiplier}x)")
            elif multiplier == 0:
                immunities.append(type_name)
        
        # Format offensive matchups
        strong_against = []
        weak_against = []
        no_effect = []
        
        for type_name, multiplier in pokemon_data['type_matchups']['attacking'].items():
            if multiplier > 1:
                strong_against.append(f"{type_name} ({multiplier}x)")
            elif multiplier < 1 and multiplier > 0:
                weak_against.append(f"{type_name} ({multiplier}x)")
            elif multiplier == 0:
                no_effect.append(type_name)
        
        # Format role information differently for own vs opponent Pokemon
        role_info = []
        rbd = pokemon_data.get('random_battle_data', {})
        is_own_pokemon = 'known_data' in pokemon_data  # Flag added by get_pokemon_complete_data
        
        if is_own_pokemon:
            # For own Pokemon, just show the role and actual stats/moves
            if rbd.get('roles'):
                role_info.append(f"Role: {', '.join(rbd['roles'])}")
            if rbd.get('level'):
                role_info.append(f"Level: {rbd['level']}")
        else:
            # For opponent Pokemon, show all possibilities
            if rbd.get('roles'):
                role_info.append(f"Possible Roles: {', '.join(rbd['roles'])}")
            if rbd.get('level'):
                role_info.append(f"Level: {rbd['level']}")
            if rbd.get('abilities'):
                role_info.append(f"Possible Abilities: {', '.join(rbd['abilities'])}")
            if rbd.get('items'):
                role_info.append(f"Possible Items: {', '.join(rbd['items'])}")
            if rbd.get('moves'):
                role_info.append(f"Possible Moves: {', '.join(rbd['moves'])}")
            if rbd.get('tera_types'):
                role_info.append(f"Possible Tera Types: {', '.join(rbd['tera_types'])}")
        
        formatted_data = f"""Pokemon Information:
        Name: {pokemon_data['pokemon_name']}
        Type: {pokemon_data['type1']}{f"/{pokemon_data['type2']}" if pokemon_data['type2'] else ""}
        Tier: {pokemon_data['tier']}

        Base Stats:
        HP: {pokemon_data['hp']}
        Attack: {pokemon_data['atk']}
        Defense: {pokemon_data['def']}
        Special Attack: {pokemon_data['spa']}
        Special Defense: {pokemon_data['spd']}
        Speed: {pokemon_data['spe']}

        Battle Information:
        {chr(10).join(f"    {info}" for info in role_info)}

        Defensive Type Matchups:
        Takes Super Effective Damage From: {', '.join(weaknesses) if weaknesses else 'None'}
        Resists Damage From: {', '.join(resistances) if resistances else 'None'}
        Immune To: {', '.join(immunities) if immunities else 'None'}

        Offensive Type Matchups:
        Super Effective Against: {', '.join(strong_against) if strong_against else 'None'}
        Not Very Effective Against: {', '.join(weak_against) if weak_against else 'None'}
        No Effect Against: {', '.join(no_effect) if no_effect else 'None'}

        Strategy:
        {pokemon_data['strategy'] if pokemon_data['strategy'] else 'No strategy information available.'}
        """
        self.logger.info(f"Final formatted data:\n{formatted_data}")
        return formatted_data

    def run(self, query: str):
        """Enhanced query-response interaction with Pokemon data integration"""
        self.logger.info(f"Processing query: {query}")
        try:
            response = self.llm.invoke(query)
            self.logger.debug(f"LLM response:\n{response}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"