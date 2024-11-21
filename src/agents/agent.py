import os
import logging
import json
from typing import Dict, Any, List, Optional, Set
from dotenv import load_dotenv
from .model_wrappers.api_gateway import APIGateway
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from pathlib import Path
import yaml
from .pokemon_db_tools import PokemonDBTools

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PSAgent')
    

class PSAgent:
    def __init__(self, api_key: Optional[str] = None, db_params: Dict[str, str] = None, personality: str = "npc"):
        """
        Initialize the Pokemon Showdown agent with database support
        
        Args:
            api_key: Optional API key to override .env file
            db_params: Database connection parameters
            personality: Personality type to load from prompts directory (default: npc)
        """
        self.logger = logging.getLogger('PSAgent.Main')
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv("SAMBANOVA_API_KEY")
        if not self.api_key:
            self.logger.error("No API key provided")
            raise ValueError("SAMBANOVA_API_KEY must be set in .env file or passed to constructor")
            
        # Load personality prompt
        self.personality_prompt = self._load_personality_prompt(personality)
        
        # Initialize the LLM
        self.logger.info("Initializing LLM")
        self.llm = self._init_llm()
        
        # Initialize DB tools
        self.logger.info("Initializing DB tools")
        self.db_tools = PokemonDBTools(db_params)

    def _load_personality_prompt(self, personality: str) -> str:
        """Load personality prompt from YAML file"""
        current_dir = Path(__file__).parent
        prompts_dir = current_dir.parent / "prompts"
        prompt_path = prompts_dir / f"{personality}.yaml"
        
        try:
            with open(prompt_path, "r") as f:
                prompt_data = yaml.safe_load(f)
                return prompt_data["system_prompt"]
        except FileNotFoundError:
            raise ValueError(f"Personality file not found: {prompt_path}")
        except KeyError:
            raise ValueError(f"Invalid personality file format: {prompt_path}")
    
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
            # Prepend personality prompt to query
            full_query = f"{self.personality_prompt}\n\n{query}"
            response = self.llm.invoke(full_query)
            self.logger.debug(f"LLM response:\n{response}")
            return response
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"