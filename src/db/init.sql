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