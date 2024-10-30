import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from model_wrappers.api_gateway import APIGateway
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

    def calculate_type_matchups(self, type1: str, type2: Optional[str] = None) -> Dict[str, float]:
        """Calculate defensive type matchups for a Pokemon"""
        self.logger.info(f"Calculating type matchups for type1={type1}, type2={type2}")
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get multipliers for type1
                self.logger.debug(f"Fetching multipliers for type1: {type1}")
                cur.execute("""
                    SELECT * FROM types WHERE type_name = %s
                """, (type1,))
                type1_data = cur.fetchone()
                
                if not type1_data:
                    self.logger.error(f"No data found for type: {type1}")
                    return {}
                
                self.logger.debug(f"Type1 data: {type1_data}")
                
                # Initialize matchups with type1 multipliers
                matchups = {k.replace('_multiplier', ''): float(v) 
                          for k, v in dict(type1_data).items() 
                          if k.endswith('_multiplier')}
                
                # If there's a second type, multiply its effectiveness
                if type2:
                    self.logger.debug(f"Fetching multipliers for type2: {type2}")
                    cur.execute("""
                        SELECT * FROM types WHERE type_name = %s
                    """, (type2,))
                    type2_data = cur.fetchone()
                    
                    if not type2_data:
                        self.logger.error(f"No data found for type: {type2}")
                    else:
                        self.logger.debug(f"Type2 data: {type2_data}")
                        for type_name in matchups:
                            multiplier_key = f"{type_name}_multiplier"
                            matchups[type_name] *= float(type2_data[multiplier_key])
                
                self.logger.info(f"Final type matchups: {matchups}")
                return matchups

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
        """Format Pokemon data for the LLM"""
        self.logger.info("Formatting Pokemon data for LLM")
        
        if "error" in pokemon_data:
            self.logger.error(f"Error in Pokemon data: {pokemon_data['error']}")
            return pokemon_data["error"]
            
        # Format type matchups into weaknesses and resistances
        weaknesses = []
        resistances = []
        immunities = []
        
        for type_name, multiplier in pokemon_data['type_matchups'].items():
            if multiplier > 1:
                weaknesses.append(f"{type_name} ({multiplier}x)")
            elif multiplier < 1 and multiplier > 0:
                resistances.append(f"{type_name} ({multiplier}x)")
            elif multiplier == 0:
                immunities.append(type_name)
        
        self.logger.debug(f"Formatted weaknesses: {weaknesses}")
        self.logger.debug(f"Formatted resistances: {resistances}")
        self.logger.debug(f"Formatted immunities: {immunities}")
                
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

Type Matchups:
Weaknesses: {', '.join(weaknesses) if weaknesses else 'None'}
Resistances: {', '.join(resistances) if resistances else 'None'}
Immunities: {', '.join(immunities) if immunities else 'None'}

Strategy:
{pokemon_data['strategy'] if pokemon_data['strategy'] else 'No strategy information available.'}
"""
        self.logger.debug(f"Final formatted data:\n{formatted_data}")
        return formatted_data

    def run(self, query: str):
        """Enhanced query-response interaction with Pokemon data integration"""
        self.logger.info(f"Processing query: {query}")
        try:
            # Check if the query is asking about a specific Pokemon
            pokemon_name = None
            query_lower = query.lower()
            
            # Look for patterns like "tell me about [pokemon]" or "what is [pokemon]"
            common_patterns = ["tell me about ", "what is ", "info on ", "information about "]
            for pattern in common_patterns:
                if pattern in query_lower:
                    potential_name = query_lower.split(pattern)[-1].strip().strip('?').title()
                    self.logger.debug(f"Found potential Pokemon name: {potential_name}")
                    pokemon_data = self.db_tools.get_pokemon_complete_data(potential_name)
                    if 'error' not in pokemon_data:
                        pokemon_name = potential_name
                        self.logger.info(f"Confirmed valid Pokemon name: {pokemon_name}")
                        break
            
            if pokemon_name:
                self.logger.info(f"Retrieving data for Pokemon: {pokemon_name}")
                pokemon_data = self.db_tools.get_pokemon_complete_data(pokemon_name)
                formatted_data = self.format_pokemon_data(pokemon_data)
                
                # Combine the formatted data with the LLM response
                enhanced_query = f"""Based on the following Pokemon data, please answer this query: {query}

{formatted_data}. The focus is to discuss the pokemon's usage within competitive pokemon. Go into detail about
how it can be used competitively, its abilities, typing advantages and disadvantages, and stats."""
                
                self.logger.debug(f"Enhanced query for LLM:\n{enhanced_query}")
                response = self.llm.invoke(enhanced_query)
                self.logger.debug(f"LLM response:\n{response}")
            else:
                self.logger.info("No Pokemon name found in query, passing directly to LLM")
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