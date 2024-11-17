import json
import psycopg2
from pathlib import Path
import re

def generate_key(name):
    """Convert a name to the Pokemon Showdown format (lowercase, no spaces or special characters)"""
    if not name:
        return None
    # Remove spaces and special characters, convert to lowercase
    key = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
    return key

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
        return format  # Returns the first format if it exists
    return None

def get_strategy_text(pokemon_name, descriptions_data):
    if pokemon_name not in descriptions_data:
        return None
    
    text = descriptions_data[pokemon_name]['text']
    if text.lower() in ['outdated', 'no content']:
        return None
    return text

def create_tables(cursor):
    print("Creating tables...")
    cursor.execute("""
        DROP TABLE IF EXISTS random_battle_sets CASCADE;
        DROP TABLE IF EXISTS pokemon CASCADE;
        DROP TABLE IF EXISTS moves CASCADE;
        DROP TABLE IF EXISTS items CASCADE;
        DROP TABLE IF EXISTS abilities CASCADE;
        DROP TABLE IF EXISTS types_defending CASCADE;
        DROP TABLE IF EXISTS types_attacking CASCADE;

        -- Create types table first since it will be referenced by pokemon
        CREATE TABLE types_attacking (
            attacking_type VARCHAR(20),
            defending_type VARCHAR(20),
            multiplier DECIMAL,
            PRIMARY KEY (attacking_type, defending_type)
        );

        CREATE TABLE types_defending (
            attacking_type VARCHAR(20),
            defending_type VARCHAR(20),
            multiplier DECIMAL,
            PRIMARY KEY (attacking_type, defending_type)
        );

        -- Create abilities table before pokemon since it will be referenced
        CREATE TABLE abilities (
            ability_name VARCHAR(255) PRIMARY KEY,
            key VARCHAR(255) UNIQUE NOT NULL,
            description TEXT NOT NULL
        );

        -- Create items table
        CREATE TABLE items (
            item_name VARCHAR(255) PRIMARY KEY,
            key VARCHAR(255) UNIQUE NOT NULL,
            description TEXT NOT NULL
        );

        -- Create moves table
        CREATE TABLE moves (
            move_name VARCHAR(255) PRIMARY KEY,
            key VARCHAR(255) UNIQUE NOT NULL,
            type VARCHAR(255),
            power VARCHAR(255),
            accuracy VARCHAR(255),
            pp VARCHAR(255),
            description TEXT
        );

        -- Create pokemon table with single tier
        CREATE TABLE pokemon (
            pokemon_name VARCHAR(255) PRIMARY KEY,
            key VARCHAR(255) UNIQUE NOT NULL,
            type1 VARCHAR(255),
            type2 VARCHAR(255),
            ability1 VARCHAR(255) REFERENCES abilities(ability_name),
            ability2 VARCHAR(255) REFERENCES abilities(ability_name),
            ability3 VARCHAR(255) REFERENCES abilities(ability_name),
            tier VARCHAR(255),
            strategy TEXT,
            hp INTEGER NOT NULL,
            atk INTEGER NOT NULL,
            def INTEGER NOT NULL,
            spa INTEGER NOT NULL,
            spd INTEGER NOT NULL,
            spe INTEGER NOT NULL
        );

        -- Create random battles roles table
        CREATE TABLE random_battle_sets (
            pokemon_name VARCHAR(255) REFERENCES pokemon(pokemon_name),
            role_name VARCHAR(255),
            level INTEGER NOT NULL,
            abilities JSONB,
            items JSONB,
            tera_types JSONB,
            moves JSONB,
            evs JSONB,
            ivs JSONB,
            PRIMARY KEY (pokemon_name, role_name)
        );

        -- Create indexes for better query performance
        CREATE INDEX idx_random_battle_sets_pokemon ON random_battle_sets(pokemon_name);
        CREATE INDEX idx_random_battle_sets_role ON random_battle_sets(role_name);
        CREATE INDEX idx_pokemon_type1 ON pokemon(type1);
        CREATE INDEX idx_pokemon_type2 ON pokemon(type2);
        CREATE INDEX idx_moves_type ON moves(type);
        CREATE INDEX idx_pokemon_tier ON pokemon(tier);
        CREATE INDEX idx_pokemon_key ON pokemon(key);
        CREATE INDEX idx_abilities_key ON abilities(key);
        CREATE INDEX idx_items_key ON items(key);
        CREATE INDEX idx_moves_key ON moves(key);
    """)
    print("Tables created successfully!")

def insert_pokemon(cursor, pokemon_data, descriptions_data):
    print(f"Inserting {len(pokemon_data)} pokemon...")
    for pokemon in pokemon_data:
        try:
            tier = get_valid_tier(pokemon.get('formats', []))
            
            type1, type2 = parse_types(pokemon['type1'])
            if pokemon.get('type2'):
                _, type2 = parse_types(pokemon['type2'])
            
            strategy = get_strategy_text(pokemon['name'], descriptions_data)
            
            cursor.execute("""
                INSERT INTO pokemon (
                    pokemon_name, key, type1, type2, ability1, ability2, ability3,
                    tier, hp, atk, def, spa, spd, spe, strategy
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                pokemon['name'],
                generate_key(pokemon['name']),
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

def insert_random_battles(cursor, random_battles_data):
    print(f"Inserting random battles data...")
    for pokemon_name, data in random_battles_data.items():
        try:
            # Insert each role as a separate entry
            for role_name, role_data in data.get('roles', {}).items():
                cursor.execute("""
                    INSERT INTO random_battle_sets (
                        pokemon_name, role_name, level, abilities, items, 
                        tera_types, moves, evs, ivs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    pokemon_name,
                    role_name,
                    data.get('level'),
                    json.dumps(role_data.get('abilities', [])),
                    json.dumps(role_data.get('items', [])),
                    json.dumps(role_data.get('teraTypes', [])),
                    json.dumps(role_data.get('moves', [])),
                    json.dumps(role_data.get('evs', {})),
                    json.dumps(role_data.get('ivs', {}))
                ))
                print(f"Inserted random battle set for {pokemon_name} - {role_name}")
        except Exception as e:
            print(f"Error inserting random battle data for {pokemon_name}: {e}")

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
                "INSERT INTO abilities (ability_name, key, description) VALUES (%s, %s, %s)",
                (ability['name'], generate_key(ability['name']), ability['description'])
            )
            print(f"Inserted ability: {ability['name']}")
        except Exception as e:
            print(f"Error inserting ability {ability['name']}: {e}")

def insert_items(cursor, items_data):
    print(f"Inserting {len(items_data)} items...")
    for item in items_data:
        try:
            cursor.execute(
                "INSERT INTO items (item_name, key, description) VALUES (%s, %s, %s)",
                (item['name'], generate_key(item['name']), item['description'])
            )
            print(f"Inserted item: {item['name']}")
        except Exception as e:
            print(f"Error inserting item {item['name']}: {e}")

def insert_moves(cursor, moves_data):
    print(f"Inserting {len(moves_data)} moves...")
    for move in moves_data:
        try:
            cursor.execute(
                """
                INSERT INTO moves (move_name, key, type, power, accuracy, pp, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    move['name'],
                    generate_key(move['name']),
                    move['type'],
                    move.get('power', None),
                    move.get('accuracy', None),
                    move.get('pp', None),
                    move.get('description', None)
                )
            )
            print(f"Inserted move: {move['name']}")
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
    
    # Load all JSON files
    print("Loading JSON files...")
    files = {
        'types': load_json_file(data_dir / 'smogon_types.json'),
        'abilities': load_json_file(data_dir / 'smogon_abilities.json'),
        'items': load_json_file(data_dir / 'smogon_items.json'),
        'moves': load_json_file(data_dir / 'smogon_moves.json'),
        'pokemon': load_json_file(data_dir / 'smogon_pokemon.json'),
        'descriptions': load_json_file(data_dir / 'pokemon_descriptions.json'),
        'random_battles': load_json_file(data_dir / 'gen9randombattle.json')
    }
    print("JSON files loaded successfully!")

    try:
        print("Connecting to database...")
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Create all tables
        create_tables(cursor)
        conn.commit()
        print("Tables created successfully!")

        # Insert all data
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

        insert_random_battles(cursor, files['random_battles'])
        conn.commit()
        print("Random battles data inserted successfully")

        print("All data inserted successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    main()