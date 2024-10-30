import json
import psycopg2
from pathlib import Path

def load_json_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def clean_stat(stat_str):
    if isinstance(stat_str, str):
        return int(stat_str.split('\n')[-1])
    return stat_str

def parse_types(type_str):
    if not type_str:
        return None, None
    types = type_str.split('\n')
    if len(types) >= 2:
        return types[0], types[1]
    return types[0], None

def clean_ability(ability_str):
    if isinstance(ability_str, str):
        return ability_str.split('\n')[0].strip()
    return ability_str

def get_valid_tier(formats):
    if not formats:
        return None
    for format in formats:
        if not format.startswith("National Dex"):
            return format
    return None

def get_strategy_text(pokemon_name, descriptions_data):
    if pokemon_name not in descriptions_data:
        return None
    
    text = descriptions_data[pokemon_name]['text']
    if text.lower() in ['outdated', 'no content']:
        return None
    return text

def insert_pokemon(cursor, pokemon_data, descriptions_data):
    print(f"Inserting {len(pokemon_data)} pokemon...")
    for pokemon in pokemon_data:
        try:
            # Get valid tier (non-National Dex)
            tier = get_valid_tier(pokemon.get('formats', []))
            if not tier:  # Skip pokemon without valid tiers
                print(f"Skipping {pokemon['name']} - no valid tier")
                continue

            type1, type2 = parse_types(pokemon['type1'])
            if pokemon.get('type2'):  # If type2 exists in the data, override the parsed type2
                _, type2 = parse_types(pokemon['type2'])
            
            # Get strategy text
            strategy = get_strategy_text(pokemon['name'], descriptions_data)
            
            # Insert the main pokemon data
            cursor.execute("""
                INSERT INTO pokemon (
                    pokemon_name, type1, type2, ability1, ability2, ability3,
                    tier, hp, atk, def, spa, spd, spe, strategy
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                clean_stat(pokemon['spe']),
                strategy
            ))
            print(f"Inserted pokemon: {pokemon['name']}")
        except Exception as e:
            print(f"Error inserting pokemon {pokemon['name']}: {e}")

def insert_type_matchups(cursor, types_data):
    print("Inserting attacking type matchups...")
    for entry in types_data['attacking_matchups']:
        attacking_type = entry['type']
        for defending_type, multiplier in entry['matchups'].items():
            try:
                cursor.execute(
                    """
                    INSERT INTO types_attacking 
                    (attacking_type, defending_type, multiplier) 
                    VALUES (%s, %s, %s)
                    """,
                    (attacking_type, defending_type, multiplier)
                )
            except Exception as e:
                print(f"Error inserting attacking matchup {attacking_type} vs {defending_type}: {e}")

    print("Inserting defending type matchups...")
    for entry in types_data['defending_matchups']:
        defending_type = entry['type']
        for attacking_type, multiplier in entry['matchups'].items():
            try:
                cursor.execute(
                    """
                    INSERT INTO types_defending 
                    (attacking_type, defending_type, multiplier) 
                    VALUES (%s, %s, %s)
                    """,
                    (attacking_type, defending_type, multiplier)
                )
            except Exception as e:
                print(f"Error inserting defending matchup {attacking_type} vs {defending_type}: {e}")

def insert_abilities(cursor, abilities_data):
    print(f"Inserting {len(abilities_data)} abilities...")
    for ability in abilities_data:
        try:
            cursor.execute(
                "INSERT INTO abilities (ability_name, description) VALUES (%s, %s)",
                (ability['name'], ability['description'])
            )
        except Exception as e:
            print(f"Error inserting ability {ability['name']}: {e}")

def insert_items(cursor, items_data):
    print(f"Inserting {len(items_data)} items...")
    for item in items_data:
        try:
            cursor.execute(
                "INSERT INTO items (item_name, description) VALUES (%s, %s)",
                (item['name'], item['description'])
            )
        except Exception as e:
            print(f"Error inserting item {item['name']}: {e}")

def insert_moves(cursor, moves_data):
    print(f"Inserting {len(moves_data)} moves...")
    for move in moves_data:
        try:
            cursor.execute(
                """
                INSERT INTO moves (move_name, type, power, accuracy, pp, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    move['name'],
                    move['type'],
                    move.get('power', None),
                    move.get('accuracy', None),
                    move.get('pp', None),
                    move.get('description', None)
                )
            )
        except Exception as e:
            print(f"Error inserting move {move['name']}: {e}")

def main():
    db_params = {
        'dbname': 'pokemon',
        'user': 'postgres',
        'password': 'password',
        'host': 'localhost',
        'port': '5432'
    }

    data_dir = Path('../scrapers/data')
    
    files = {
        'types': load_json_file(data_dir / 'smogon_types.json'),
        'abilities': load_json_file(data_dir / 'smogon_abilities.json'),
        'items': load_json_file(data_dir / 'smogon_items.json'),
        'moves': load_json_file(data_dir / 'smogon_moves.json'),
        'pokemon': load_json_file(data_dir / 'smogon_pokemon.json'),
        'descriptions': load_json_file(data_dir / 'pokemon_descriptions.json')
    }

    try:
        print("Connecting to database...")
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Insert data
        insert_type_matchups(cursor, files['types'])
        conn.commit()
        print("Types inserted successfully")

        insert_abilities(cursor, files['abilities'])
        conn.commit()
        print("Abilities inserted successfully")

        insert_items(cursor, files['items'])
        conn.commit()
        print("Items inserted successfully")

        insert_moves(cursor, files['moves'])
        conn.commit()
        print("Moves inserted successfully")

        insert_pokemon(cursor, files['pokemon'], files['descriptions'])
        conn.commit()
        print("Pokemon inserted successfully")

        print("All data inserted successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()