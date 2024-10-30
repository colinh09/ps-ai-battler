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
    description TEXT NOT NULL
);

-- Create items table
CREATE TABLE items (
    item_name VARCHAR(255) PRIMARY KEY,
    description TEXT NOT NULL
);

-- Create moves table
CREATE TABLE moves (
    move_name VARCHAR(255) PRIMARY KEY,
    type VARCHAR(255),
    power VARCHAR(255),
    accuracy VARCHAR(255),
    pp VARCHAR(255),
    description TEXT
);

-- Create pokemon table with single tier
CREATE TABLE pokemon (
    pokemon_name VARCHAR(255) PRIMARY KEY,
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

-- Create indexes for better query performance
CREATE INDEX idx_pokemon_type1 ON pokemon(type1);
CREATE INDEX idx_pokemon_type2 ON pokemon(type2);
CREATE INDEX idx_moves_type ON moves(type);
CREATE INDEX idx_pokemon_tier ON pokemon(tier);