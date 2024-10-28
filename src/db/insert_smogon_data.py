import json
import psycopg2
from psycopg2.extras import execute_values
import os
from pathlib import Path

def load_json_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def clean_stat(stat_str):
    """Clean stat strings like 'HP\n90' to just the number"""
    if isinstance(stat_str, str):
        return int(stat_str.split('\n')[-1])
    return stat_str

def parse_types(type_str):
    """Parse type string into two types"""
    if not type_str:
        return None, None
    types = type_str.split('\n')
    if len(types) >= 2:
        return types[0], types[1]
    return types[0], None

def clean_ability(ability_str):
    """Clean ability strings by taking only the first line"""
    if isinstance(ability_str, str):
        return ability_str.split('\n')[0].strip()
    return ability_str

def get_valid_tier(formats):
    """Get the first non-National Dex tier from formats"""
    if not formats:
        return None
    for format in formats:
        if not format.startswith("National Dex"):
            return format
    return None

def insert_types(cursor, types_data):
    print("Inserting types...")
    for type_entry in types_data['type_matchups']:
        type_name = type_entry['type']
        matchups = type_entry['matchups']
        
        cursor.execute("""
            INSERT INTO types (
                type_name, bug_multiplier, dark_multiplier, dragon_multiplier,
                electric_multiplier, fairy_multiplier, fighting_multiplier,
                fire_multiplier, flying_multiplier, ghost_multiplier,
                grass_multiplier, ground_multiplier, ice_multiplier,
                normal_multiplier, poison_multiplier, psychic_multiplier,
                rock_multiplier, steel_multiplier, stellar_multiplier,
                water_multiplier
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            type_name, matchups['Bug'], matchups['Dark'], matchups['Dragon'],
            matchups['Electric'], matchups['Fairy'], matchups['Fighting'],
            matchups['Fire'], matchups['Flying'], matchups['Ghost'],
            matchups['Grass'], matchups['Ground'], matchups['Ice'],
            matchups['Normal'], matchups['Poison'], matchups['Psychic'],
            matchups['Rock'], matchups['Steel'], matchups['Stellar'],
            matchups['Water']
        ))

def insert_abilities(cursor, abilities_data):
    print("Inserting abilities...")
    execute_values(cursor,
        "INSERT INTO abilities (ability_name, description) VALUES %s",
        [(ability['name'], ability['description']) for ability in abilities_data]
    )

def insert_items(cursor, items_data):
    print("Inserting items...")
    execute_values(cursor,
        "INSERT INTO items (item_name, description) VALUES %s",
        [(item['name'], item['description']) for item in items_data]
    )

def insert_moves(cursor, moves_data):
    print("Inserting moves...")
    execute_values(cursor,
        """
        INSERT INTO moves (move_name, type, power, accuracy, pp, description)
        VALUES %s
        """,
        [(
            move['name'],
            move['type'],
            move.get('power', None),
            move.get('accuracy', None),
            move.get('pp', None),
            move.get('description', None)
        ) for move in moves_data]
    )

def insert_pokemon(cursor, pokemon_data):
    print("Inserting pokemon...")
    for pokemon in pokemon_data:
        # Get valid tier (non-National Dex)
        tier = get_valid_tier(pokemon.get('formats', []))
        if not tier:  # Skip pokemon without valid tiers
            continue

        type1, type2 = parse_types(pokemon['type1'])
        if pokemon.get('type2'):  # If type2 exists in the data, override the parsed type2
            _, type2 = parse_types(pokemon['type2'])
        
        # Insert the main pokemon data
        cursor.execute("""
            INSERT INTO pokemon (
                pokemon_name, type1, type2, ability1, ability2, ability3,
                tier, hp, atk, def, spa, spd, spe
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            pokemon['name'],
            type1,
            type2,
            clean_ability(pokemon.get('ability1')),
            clean_ability(pokemon.get('ability2')),
            clean_ability(pokemon.get('ability3')),
            tier,
            clean_stat(pokemon['hp']),
            clean_stat(pokemon['atk']),
            clean_stat(pokemon['def']),
            clean_stat(pokemon['spa']),
            clean_stat(pokemon['spd']),
            clean_stat(pokemon['spe'])
        ))

def main():
    # Database connection parameters
    db_params = {
        'dbname': 'pokemon',
        'user': 'postgres',
        'password': 'password',
        'host': 'localhost',
        'port': '5432'
    }

    # Path to data files
    data_dir = Path('../scrapers/data')
    
    # Load all JSON files
    files = {
        'types': load_json_file(data_dir / 'smogon_types.json'),
        'abilities': load_json_file(data_dir / 'smogon_abilities.json'),
        'items': load_json_file(data_dir / 'smogon_items.json'),
        'moves': load_json_file(data_dir / 'smogon_moves.json'),
        'pokemon': load_json_file(data_dir / 'smogon_pokemon.json')
    }

    try:
        # Connect to the database
        print("Connecting to database...")
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Insert data in the correct order (due to foreign key constraints)
        insert_types(cursor, files['types'])
        insert_abilities(cursor, files['abilities'])
        insert_items(cursor, files['items'])
        insert_moves(cursor, files['moves'])
        insert_pokemon(cursor, files['pokemon'])

        # Commit the transaction
        conn.commit()
        print("Data insertion completed successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()