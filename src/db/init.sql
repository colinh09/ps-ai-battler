-- Create types table first since it will be referenced by pokemon
CREATE TABLE types (
    type_name VARCHAR(255) PRIMARY KEY,
    bug_multiplier DECIMAL(3,1) NOT NULL,
    dark_multiplier DECIMAL(3,1) NOT NULL,
    dragon_multiplier DECIMAL(3,1) NOT NULL,
    electric_multiplier DECIMAL(3,1) NOT NULL,
    fairy_multiplier DECIMAL(3,1) NOT NULL,
    fighting_multiplier DECIMAL(3,1) NOT NULL,
    fire_multiplier DECIMAL(3,1) NOT NULL,
    flying_multiplier DECIMAL(3,1) NOT NULL,
    ghost_multiplier DECIMAL(3,1) NOT NULL,
    grass_multiplier DECIMAL(3,1) NOT NULL,
    ground_multiplier DECIMAL(3,1) NOT NULL,
    ice_multiplier DECIMAL(3,1) NOT NULL,
    normal_multiplier DECIMAL(3,1) NOT NULL,
    poison_multiplier DECIMAL(3,1) NOT NULL,
    psychic_multiplier DECIMAL(3,1) NOT NULL,
    rock_multiplier DECIMAL(3,1) NOT NULL,
    steel_multiplier DECIMAL(3,1) NOT NULL,
    stellar_multiplier DECIMAL(3,1) NOT NULL,
    water_multiplier DECIMAL(3,1) NOT NULL
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
    type VARCHAR(255) NOT NULL REFERENCES types(type_name),
    power VARCHAR(255),
    accuracy VARCHAR(255),
    pp VARCHAR(255),
    description TEXT
);

-- Create pokemon table with single tier
CREATE TABLE pokemon (
    pokemon_name VARCHAR(255) PRIMARY KEY,
    type1 VARCHAR(255) NOT NULL REFERENCES types(type_name),
    type2 VARCHAR(255) REFERENCES types(type_name),
    ability1 VARCHAR(255) REFERENCES abilities(ability_name),
    ability2 VARCHAR(255) REFERENCES abilities(ability_name),
    ability3 VARCHAR(255) REFERENCES abilities(ability_name),
    tier VARCHAR(255),  -- Changed to single tier
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