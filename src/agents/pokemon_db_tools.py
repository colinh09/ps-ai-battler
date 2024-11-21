import psycopg2
from psycopg2.extras import RealDictCursor
import json
from typing import Dict, Any, List, Optional, Set
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class PokemonDBTools:
    def __init__(self, db_params: Dict[str, str]):
        """Initialize database connection and ensure pg_trgm extension is enabled"""
        self.db_params = db_params
        self.logger = logging.getLogger('PSAgent.DBTools')
        
        # Enable pg_trgm extension if not already enabled
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                conn.commit()
    
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
        Uses PostgreSQL fuzzy matching to find similar Pokemon names.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # For agent Pokemon with known_data, try exact key first
                if known_data:
                    pokemon_key = pokemon_name.lower().replace(' ', '')
                    cur.execute("""
                        SELECT *, similarity(pokemon_name, %s) as match_score 
                        FROM pokemon 
                        WHERE key = %s
                    """, (pokemon_name, pokemon_key))
                    pokemon_data = cur.fetchone()
                    
                    if pokemon_data:
                        self.logger.debug(f"Found exact match by key for {pokemon_name}")
                    else:
                        # If no exact match, try fuzzy match
                        cur.execute("""
                            SELECT *, similarity(pokemon_name, %s) as match_score
                            FROM pokemon
                            WHERE similarity(pokemon_name, %s) > 0.3
                            ORDER BY similarity(pokemon_name, %s) DESC
                            LIMIT 1
                        """, (pokemon_name, pokemon_name, pokemon_name))
                        pokemon_data = cur.fetchone()
                else:
                    # For opponent Pokemon, go straight to fuzzy matching
                    cur.execute("""
                        SELECT *, similarity(pokemon_name, %s) as match_score
                        FROM pokemon
                        WHERE similarity(pokemon_name, %s) > 0.3
                        ORDER BY similarity(pokemon_name, %s) DESC
                        LIMIT 1
                    """, (pokemon_name, pokemon_name, pokemon_name))
                    pokemon_data = cur.fetchone()

                if not pokemon_data:
                    self.logger.error(f"No Pokemon found (even with fuzzy match) for: {pokemon_name}")
                    return {
                        'pokemon_name': pokemon_name,
                        'type1': 'Unknown',
                        'type2': None,
                        'tier': 'Unknown',
                        'hp': 100,
                        'atk': 100,
                        'def': 100,
                        'spa': 100,
                        'spd': 100,
                        'spe': 100,
                        'abilities': [],
                        'type_matchups': {
                            'defending': {},
                            'attacking': {}
                        },
                        'random_battle_data': {},
                        'strategy': 'No strategy information available.'
                    }

                self.logger.info(f"Matched '{pokemon_name}' to '{pokemon_data['pokemon_name']}' with score {pokemon_data['match_score']}")
                
                # Get random battle data using the matched name
                random_battle_data = self.get_best_random_battle_set(pokemon_data['pokemon_name'], known_data)
                
                result = dict(pokemon_data)
                if known_data:
                    result['known_data'] = known_data

                # Get ability descriptions
                abilities = []
                for ability_key in ['ability1', 'ability2', 'ability3']:
                    if result[ability_key]:
                        ability_data = self.get_ability_data(result[ability_key])
                        if ability_data:
                            abilities.append({
                                'name': ability_data['ability_name'],
                                'description': ability_data['description']
                            })
                
                result['abilities'] = abilities
                result['type_matchups'] = self.calculate_type_matchups(
                    result['type1'],
                    result['type2']
                )
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

    def batch_pokemon_lookup(
        self, 
        pokemon_names: List[str], 
        include_randbats: bool = False,
        known_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Look up complete data for multiple Pokemon, optionally including random battle data.
        
        Args:
            pokemon_names: List of Pokemon names to look up
            include_randbats: Whether to include random battle set data
            known_data: Optional dict of known data for agent's Pokemon
            
        Returns:
            List of dicts containing complete Pokemon data
        """
        self.logger.info(f"Looking up data for Pokemon: {pokemon_names}")
        results = []
        
        for pokemon_name in pokemon_names:
            try:
                # Get complete Pokemon data
                pokemon_data = self.get_pokemon_complete_data(pokemon_name, known_data)
                
                if not pokemon_data:
                    self.logger.warning(f"No data found for Pokemon: {pokemon_name}")
                    continue
                    
                # Remove random battle data if not requested
                if not include_randbats:
                    pokemon_data.pop('random_battle_data', None)
                
                # Organize the response data
                organized_data = {
                    'pokemon_name': pokemon_data['pokemon_name'],
                    'types': [pokemon_data['type1']],
                    'base_stats': {
                        'hp': pokemon_data['hp'],
                        'atk': pokemon_data['atk'],
                        'def': pokemon_data['def'],
                        'spa': pokemon_data['spa'],
                        'spd': pokemon_data['spd'],
                        'spe': pokemon_data['spe']
                    },
                    'abilities': pokemon_data['abilities'],
                    'tier': pokemon_data['tier'],
                    'type_matchups': pokemon_data['type_matchups']
                }
                
                # Add second type if it exists
                if pokemon_data.get('type2'):
                    organized_data['types'].append(pokemon_data['type2'])
                
                # Add strategy if available
                if pokemon_data.get('strategy'):
                    organized_data['strategy'] = pokemon_data['strategy']
                    
                # Add random battle data if requested
                if include_randbats and pokemon_data.get('random_battle_data'):
                    organized_data['random_battle_data'] = pokemon_data['random_battle_data']
                
                results.append(organized_data)
                print(results)
                self.logger.debug(f"Successfully looked up data for {pokemon_name}")
                
            except Exception as e:
                self.logger.error(f"Error looking up {pokemon_name}: {str(e)}", exc_info=True)
                continue
        
        return results