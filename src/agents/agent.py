import os
import logging
from typing import Optional, Dict, Any
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

class PokemonDBTools:
    def __init__(self, db_params: Dict[str, str]):
        """Initialize database connection"""
        self.db_params = db_params
        self.logger = logging.getLogger('PSAgent.DBTools')
        
    def get_connection(self):
        """Create and return a database connection"""
        self.logger.debug(f"Attempting to connect to database: {self.db_params['dbname']} at {self.db_params['host']}")
        return psycopg2.connect(**self.db_params)

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

    def get_pokemon_complete_data(self, pokemon_name: str) -> Dict[str, Any]:
        """Get complete information about a Pokemon including stats, abilities, and type matchups"""
        self.logger.info(f"Fetching complete data for Pokemon: {pokemon_name}")
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get basic Pokemon data
                self.logger.debug(f"Executing Pokemon query for: {pokemon_name}")
                cur.execute("""
                    SELECT * FROM pokemon WHERE pokemon_name = %s
                """, (pokemon_name,))
                pokemon_data = cur.fetchone()
                
                if not pokemon_data:
                    self.logger.error(f"Pokemon not found: {pokemon_name}")
                    return {"error": f"Pokemon {pokemon_name} not found"}
                
                self.logger.debug(f"Found Pokemon data: {pokemon_data}")
                result = dict(pokemon_data)
                
                # Get ability descriptions
                abilities = []
                for ability_key in ['ability1', 'ability2', 'ability3']:
                    if result[ability_key]:
                        self.logger.debug(f"Fetching ability data for: {result[ability_key]}")
                        cur.execute("""
                            SELECT * FROM abilities WHERE ability_name = %s
                        """, (result[ability_key],))
                        ability_data = cur.fetchone()
                        if ability_data:
                            self.logger.debug(f"Found ability data: {ability_data}")
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
                
                self.logger.info(f"Complete Pokemon data assembled: {result}")
                return result

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
        """Format Pokemon data for the LLM with separate offensive and defensive matchups"""
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

    Abilities:
    {chr(10).join(f"- {ability['name']}: {ability['description']}" for ability in pokemon_data['abilities'])}

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
        self.logger.debug(f"Final formatted data:\n{formatted_data}")
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

# Usage example
if __name__ == "__main__":
    db_params = {
        'dbname': 'pokemon',
        'user': 'postgres',
        'password': 'password',
        'host': 'localhost',
        'port': '5432'
    }
    
    # Initialize the agent
    agent = PSAgent(db_params=db_params)
    
    # Run a query
    response = agent.run("Tell me about Alomomola")
    print(response)