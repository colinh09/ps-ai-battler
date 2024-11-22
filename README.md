# Pokemon Battler, Companion, Rival, Teambuilder
## Overview
This project creates an agent-based chatbot that embodies different Pokemon trainer personalities, focusing on competitive Pokemon battles. The bot handles team building, battles, and strategy discussions using SambaNova Cloud models to generate responses that authentically mimic Pokemon NPCs.

## Project Objective
I have always been fascinated by game-playing AI like Deep Blue, AlphaZero, and OpenAI Five. However, state of the art game-playing AI typically rely on computationally intensive approaches such as deep reinforcement learning. More reasonable approaches such as minimax search or Monte Carlo Tree Search can be viable, but in many cases has already been done for many games, including Pokemon.

With the emergence of RAG-based AI agents and the accessibility of Pokemon Showdown data through web scraping, I saw an opportunity to take a different approach. By leveraging RAG to incorporate competitive Pokemon strategy and game state information, we can create an AI that makes informed decisions without traditional search or learning methods. The interactive nature of LLMs also enables our agent to both play strategically and roleplay as a trainer, creating an immersive battle experience that combines competitive gameplay with personality.

With this in mind, I wanted to accomplish 3 things:
1. Use RAG to help the AI make reasonable battle moves and have informed Pokemon discussions with players
2. Keep response times fast so conversations and battles feel natural, like talking to a real Pokemon NPC/trainer (doable thanks to SambaNova's "lightning fast" inference times)
3. Let the AI act as different Pokemon trainers with unique personalities and battling styles

I hope that this project provides a proof-of-concept of how game-playing AI and game NPCs can be developed using RAG-based AI (and using SambaNova Cloud API!)

## How it works

This project uses [Pokemon Showdown](https://play.pokemonshowdown.com/), which is a free, web-based Pokemon battle simulator. Pokemon Showdown allows players to battle each other using Pokemon teams without needing actual Pokemon games. The simulator follows competitive Pokemon rules established by Smogon, the largest competitive Pokemon community that creates and maintains the standard ruleset used in competitive Pokemon battles.

### Technical Implementation
The simulator is implemented using SockJS, which allows direct connection to the Pokemon Showdown client through a websocket. More details about the technical implementation can be found [here](https://github.com/smogon/pokemon-showdown/tree/master).

### Core Features

#### 1. User Interaction
- The system logs into Pokemon Showdown using provided credentials
- It starts a Direct Message (DM) conversation with a target user
- Users can interact with the agent through these DMs

#### 2. Pokemon Information Requests
When a user asks about a specific Pokemon:
- The agent extracts the Pokemon's name
- Makes a database call to retrieve:
  - Basic information (ability, type(s), competitive tier)
  - Smogon strategy guides (example: [Alomomola Strategy Guide](https://www.smogon.com/dex/sv/pokemon/alomomola/))
- Provides competitive analysis based on this information

#### 3. Battle Mode
When a user wants to battle:
- System detects battle intent
- Initiates a battle through Pokemon Showdown
- Once accepted, enters "battle mode" where it:
  - Monitors battle state updates via websocket
  - Analyzes current situation and strategy information
  - Makes optimal move decisions
  - Explains its reasoning in the battle chat
  - After the battle ends, the agent will provide an analysis of the battle

<details>
<summary>This is an example battle state the agent is given</summary>

```
Based on the following battle situation, what would be the best move to make? Consider all available moves and switches.
            
Battle History:
Pincurchin switched to Pincurchin!
Donphan switched to Donphan!

            YOUR ACTIVE POKEMON:
- Pincurchin (HP: 100.0%)
  Role: Bulky Attacker, Bulky Setup
  Type Matchups:
    Weak to: Ground (2.0x)
    Resists: Electric (0.5x), Flying (0.5x), Steel (0.5x)
  Ability: Electric Surge
    Description: On switch-in, this Pokemon summons Electric Terrain.
  Known moves:
    - Discharge (Type: Electric, Power: 80, Accuracy: 100%)
      Description: 30% chance to paralyze adjacent Pokemon.
    - Recover (Type: Normal, Power: —, Accuracy: —)
      Description: Heals the user by 50% of its max HP.
    - Scald (Type: Water, Power: 80, Accuracy: 100%)
      Description: 30% chance to burn the target. Thaws target..
    - Toxic Spikes (Type: Poison, Power: —, Accuracy: —)
      Description: Poisons grounded foes on switch-in. Max 2 layers.
  Item: Leftovers
    Description: At the end of every turn, holder restores 1/16 of its max HP.
  Base Stats:
    HP: 48
    Attack: 101
    Defense: 95
    Sp. Attack: 91
    Sp. Defense: 85
    Speed: 15
  Tera Type: Water
  Can Terastallize
  Current Stats:
    ATK: 207, DEF: 247, SPA: 239, SPD: 227, SPE: 87

OPPONENT'S ACTIVE POKEMON:
- Donphan (HP: 100.0%)
  Type Matchups:
    Weak to: Water (2.0x), Grass (2.0x), Ice (2.0x)
    Immune to: Electric
  Base Stats:
    HP: 90
    Attack: 120
    Defense: 120
    Sp. Attack: 60
    Sp. Defense: 60
    Speed: 50
  Possible Roles: Bulky Support
  Level: 84
  Possible Abilities: Sturdy
  Possible Items: Assault Vest, Choice Band, Leftovers
  Possible Moves: Earthquake, Ice Shard, Ice Spinner, Knock Off, Rapid Spin, Stealth Rock
  Possible Tera Types: Ghost, Grass

YOUR TEAM:
- Pincurchin (HP: 100.0%)
  Role: Bulky Attacker, Bulky Setup
  Ability: Electric Surge
    Description: On switch-in, this Pokemon summons Electric Terrain.
  Item: Leftovers
    Description: At the end of every turn, holder restores 1/16 of its max HP.
  Type Matchups:
    Weak to: Ground (2.0x)
    Resists: Electric (0.5x), Flying (0.5x), Steel (0.5x)
  Known moves:
    - Discharge (Type: Electric, Power: 80, Accuracy: 100%)
      Description: 30% chance to paralyze adjacent Pokemon.
    - Recover (Type: Normal, Power: —, Accuracy: —)
      Description: Heals the user by 50% of its max HP.
    - Scald (Type: Water, Power: 80, Accuracy: 100%)
      Description: 30% chance to burn the target. Thaws target..
    - Toxic Spikes (Type: Poison, Power: —, Accuracy: —)
      Description: Poisons grounded foes on switch-in. Max 2 layers.
  Base Stats:
    HP: 48
    Attack: 101
    Defense: 95
    Sp. Attack: 91
    Sp. Defense: 85
    Speed: 15
  Tera Type: Water
- Sandaconda (HP: 100.0%)
  Role: Bulky Attacker, Bulky Setup, Fast Bulky Setup
  Ability: Shed Skin
    Description: This Pokemon has a 33% chance to have its status cured at the end of each turn.
  Item: Loaded Dice
    Description: Holder's moves that hit 2-5 times hit 4-5 times; Population Bomb hits 4-10 times.
  Type Matchups:
    Weak to: Water (2.0x), Grass (2.0x), Ice (2.0x)
    Immune to: Electric
  Known moves:
    - Coil (Type: Poison, Power: —, Accuracy: —)
      Description: Raises user's Attack, Defense, accuracy by 1.
    - Rock Blast (Type: Rock, Power: 25, Accuracy: 90%)
      Description: Hits 2-5 times in one turn.
    - Scale Shot (Type: Dragon, Power: 25, Accuracy: 90%)
      Description: Hits 2-5 times. User: -1 Def, +1 Spe after last hit.
    - Earthquake (Type: Ground, Power: 100, Accuracy: 100%)
      Description: Hits adjacent Pokemon. Double damage on Dig.
  Base Stats:
    HP: 72
    Attack: 107
    Defense: 125
    Sp. Attack: 65
    Sp. Defense: 70
    Speed: 71
  Tera Type: Dragon
- Sandy Shocks (HP: 100.0%)
  Role: Fast Support
  Ability: Protosynthesis
    Description: Sunny Day active or Booster Energy used: highest stat is 1.3x, or 1.5x if Speed.
  Item: Heavy-Duty Boots
    Description: When switching in, the holder is unaffected by hazards on its side of the field.
  Type Matchups:
    Weak to: Ground (2.0x), Water (2.0x), Grass (2.0x), Ice (2.0x)
    Resists: Flying (0.5x), Steel (0.5x)
    Immune to: Electric
  Known moves:
    - Stealth Rock (Type: Rock, Power: —, Accuracy: —)
      Description: Hurts foes on switch-in. Factors Rock weakness.
    - Thunderbolt (Type: Electric, Power: 90, Accuracy: 100%)
      Description: 10% chance to paralyze the target.
    - Volt Switch (Type: Electric, Power: 70, Accuracy: 100%)
      Description: User switches out after damaging the target.
    - Earth Power (Type: Ground, Power: 90, Accuracy: 100%)
      Description: 10% chance to lower the target's Sp. Def by 1.
  Base Stats:
    HP: 85
    Attack: 81
    Defense: 97
    Sp. Attack: 121
    Sp. Defense: 85
    Speed: 101
  Tera Type: Grass
- Sudowoodo (HP: 100.0%)
  Role: Bulky Attacker
  Ability: Rock Head
    Description: This Pokemon does not take recoil damage besides Struggle/Life Orb/crash damage.
  Item: Choice Band
    Description: Holder's Attack is 1.5x, but it can only select the first move it executes.
  Type Matchups:
    Weak to: Water (2.0x), Grass (2.0x), Fighting (2.0x), Ground (2.0x), Steel (2.0x)
  Known moves:
    - Wood Hammer (Type: Grass, Power: 120, Accuracy: 100%)
      Description: Has 33% recoil.
    - Head Smash (Type: Rock, Power: 150, Accuracy: 80%)
      Description: Has 1/2 recoil.
    - Sucker Punch (Type: Dark, Power: 70, Accuracy: 100%)
      Description: Usually goes first. Fails if target is not attacking.
    - Earthquake (Type: Ground, Power: 100, Accuracy: 100%)
      Description: Hits adjacent Pokemon. Double damage on Dig.
  Base Stats:
    HP: 70
    Attack: 100
    Defense: 115
    Sp. Attack: 30
    Sp. Defense: 65
    Speed: 30
  Tera Type: Rock
- Tsareena (HP: 100.0%)
  Role: Fast Support
  Ability: Queenly Majesty
    Description: This Pokemon and its allies are protected from opposing priority moves.
  Item: Choice Scarf
    Description: Holder's Speed is 1.5x, but it can only select the first move it executes.
  Type Matchups:
    Weak to: Fire (2.0x), Ice (2.0x), Poison (2.0x), Flying (2.0x), Bug (2.0x)
    Resists: Water (0.5x), Electric (0.5x), Grass (0.5x)
  Known moves:
    - Knock Off (Type: Dark, Power: 65, Accuracy: 100%)
      Description: 1.5x damage if foe holds an item. Removes item.
    - U-turn (Type: Bug, Power: 70, Accuracy: 100%)
      Description: User switches out after damaging the target.
    - High Jump Kick (Type: Fighting, Power: 130, Accuracy: 90%)
      Description: User is hurt by 50% of its max HP if it misses.
    - Power Whip (Type: Grass, Power: 120, Accuracy: 85%)
      Description: No additional effect.
  Base Stats:
    HP: 72
    Attack: 120
    Defense: 98
    Sp. Attack: 50
    Sp. Defense: 98
    Speed: 72
  Tera Type: Fighting
- Pelipper (HP: 100.0%)
  Role: Bulky Attacker, Wallbreaker
  Ability: Drizzle
    Description: On switch-in, this Pokemon summons Rain Dance.
  Item: Choice Specs
    Description: Holder's Sp. Atk is 1.5x, but it can only select the first move it executes.
  Type Matchups:
    Weak to: Electric (4.0x), Grass (2.0x), Rock (2.0x)
    Resists: Fire (0.5x), Water (0.5x)
    Immune to: Ground
  Known moves:
    - Hydro Pump (Type: Water, Power: 110, Accuracy: 80%)
      Description: No additional effect.
    - U-turn (Type: Bug, Power: 70, Accuracy: 100%)
      Description: User switches out after damaging the target.
    - Hurricane (Type: Flying, Power: 110, Accuracy: 70%)
      Description: 30% chance to confuse target. Can't miss in rain.
    - Weather Ball (Type: Normal, Power: 50, Accuracy: 100%)
      Description: Power doubles and type varies in each weather.
  Base Stats:
    HP: 60
    Attack: 50
    Defense: 100
    Sp. Attack: 95
    Sp. Defense: 70
    Speed: 65
  Tera Type: Water

REVEALED OPPONENT POKEMON:
- Donphan (HP: 100.0%)
  Role: Bulky Support
  Type Matchups:
    Weak to: Water (2.0x), Grass (2.0x), Ice (2.0x)
    Immune to: Electric
  Base Stats:
    HP: 90
    Attack: 120
    Defense: 120
    Sp. Attack: 60
    Sp. Defense: 60
    Speed: 50

FIELD CONDITIONS:
- No active field conditions

SIDE CONDITIONS:
Your side:
Opponent's side:

AVAILABLE ACTIONS (You MUST choose ONLY from these actions):
Available moves:
- Move 1: Discharge (Type: Electric, Power: 80, Accuracy: 100%, PP: 24/24) [Can Terastallize with 'move Xt']
  Description: 30% chance to paralyze adjacent Pokemon.
- Move 2: Recover (Type: Normal, Power: —, Accuracy: —, PP: 8/8) [Can Terastallize with 'move Xt']
  Description: Heals the user by 50% of its max HP.
- Move 3: Toxic Spikes (Type: Poison, Power: —, Accuracy: —, PP: 32/32) [Can Terastallize with 'move Xt']
  Description: Poisons grounded foes on switch-in. Max 2 layers.
- Move 4: Scald (Type: Water, Power: 80, Accuracy: 100%, PP: 24/24) [Can Terastallize with 'move Xt']
  Description: 30% chance to burn the target. Thaws target.

Available switches:
- Switch 2: Sandaconda (258/258)
    Weak to: Water (2.0x), Grass (2.0x), Ice (2.0x)
    Immune to: Electric
- Switch 3: Sandy Shocks (267/267)
    Weak to: Ground (2.0x), Water (2.0x), Grass (2.0x), Ice (2.0x)
    Resists: Flying (0.5x), Steel (0.5x)
    Immune to: Electric
- Switch 4: Sudowoodo (284/284)
    Weak to: Water (2.0x), Grass (2.0x), Fighting (2.0x), Ground (2.0x), Steel (2.0x)
- Switch 5: Tsareena (267/267)
    Weak to: Fire (2.0x), Ice (2.0x), Poison (2.0x), Flying (2.0x), Bug (2.0x)
    Resists: Water (0.5x), Electric (0.5x), Grass (0.5x)
- Switch 6: Pelipper (243/243)
    Weak to: Electric (4.0x), Grass (2.0x), Rock (2.0x)
    Resists: Fire (0.5x), Water (0.5x)
    Immune to: Ground

=== END BATTLE SITUATION ===
```
</details>

#### 4. Team Building
To get help building a team, users need to specify:
- The Pokemon generation (e.g., gen9 for Sword/Shield)
- The competitive tier (e.g., OU for Overused)

The agent then:
- Uses Smogon's statistical data ([usage stats](https://www.smogon.com/stats/2024-09/gen9ou-0.txt) and [movesets](https://www.smogon.com/stats/2024-09/moveset/gen9ou-0.txt))
- Selects Pokemon based on:
  - Usage statistics
  - Team synergy
  - Current team composition
- Outputs a complete team in `src/team.txt`
- This file can be directly imported into Pokemon Showdown's team builder

#### 5. AI Model Used
The project uses the Meta Llama 3.1 70B model directly from the SambaNova Cloud API. Their models have very fast inference times, which is perfect for a project like this where it improves the immersiveness of the project a ton. To set up and use the model, I used their "enterprise knowledge retriever" example in their AI starter kit which can be found [here](https://github.com/sambanova/ai-starter-kit/tree/main/enterprise_knowledge_retriever). This basically got me up and running with model experimentation within a few hours, and was undoubtedly the easiest part of the project to set up!

#### 6. Frontend
The project uses a streamlit frontend to insert settings such as the SambaNova API key, the credentials the agent will use to login, the username of the user the agent interacts with, and the personality of the agent. The default settings must be set in a ```secrets.toml``` file prior to starting the streamlit app. More instructions on this can be found in the project set up section. Press the start button once all settings are set. 

## Demo


## Project Setup Instructions

### Prerequisites
- A SambaNova API key (You can get a free API key at https://cloud.sambanova.ai/apis)
- Python 3.12 or compatible version
- Docker and Docker Compose
- pip (Python package manager)
- git

### Installation Steps

1. Clone and enter the repository
   ```
   git clone git@github.com:colinh09/ps-ai-battler.git
   ```
   
   Enter the project directory
   ```
   cd ps-ai-battler
   ```

2. Create virtual environment
   ```
   python -m venv venv
   ```

   Activate virtual environment
   On Windows:
   ```
   .\venv\Scripts\activate
   ```
   On Unix or MacOS:
   ```
   source venv/bin/activate
   ```

3. Install requirements
    ```
   pip install -r requirements.txt
   ```

4. Navigate to the database directory
   ```
   cd src/db
   ```
   
   Start Docker container for database
   ```
   docker compose up -d
   ```

   Populate database with initial data
   ```
   python3 insert_smogon_data.py
   ```

   Return to root directory
   ```
   cd ../..
   ```

5. Navigate to src directory
   ```
   cd src
   ```

   Create .streamlit directory
   ```
   mkdir .streamlit
   ```

   Create and edit secrets.toml file
   ```
   touch .streamlit/secrets.toml
   ```

   Add the following configuration to secrets.toml. More instructions on how to obtain these variables will be detailed in the next section. 
   ```
   SAMBA_NOVA_API_KEY = "" # This project requires a Samba Nova API key
   PS_USERNAME = "" # The username the bot will log into
   PS_PASSWORD = "" # The password the bot will use to log in
   PS_TARGET_USERNAME = "" # The Pokemon Showdown account you will use
   DEFAULT_PERSONALITY = "professor"  # Options: professor, npc, arrogant rival, supportive rival
   ```

6. Run the application. Make sure the target user is logged into pokemon showdown when starting the system.
   ```
   streamlit run app.py
   ```

## Help Setting Secrets in secrets.toml
In order for the application to run, you will need 5 different variables.

1. **SambaNova API Key**: You can easily get a free API key [here](https://cloud.sambanova.ai/apis)
2. **Pokemon Showdown Credentials**: These are the credentals (```PS_USERNAME``` and ```PS_PASSWORD```) that the AI agent logs in with to interact with users. There were complications with using credentials from users that recently signed up. Therefore, I will provide accounts below that are free to use that I've had for years! Don't ask me why I have so many of them... I made these when I was in middle school. Please let me know if any of them do not work.

Account1:
```
PS_USERNAME = "rightnow2day"
PS_PASSWORD = "sambanova"
```
Account 2:
```
PS_USERNAME = "rightnow3day"
PS_PASSWORD = "sambanova"
```
Account 3:
```
PS_USERNAME = "notnow2morrow"
PS_PASSWORD = "sambanova"
```
Account 4:
```
PS_USERNAME = "notnow3morrow"
PS_PASSWORD = "sambanova"
```
Account 5:
```
PS_USERNAME = "notnow4morrow"
PS_PASSWORD = "sambanova"
```

3. **Target Username**: This is the username of the user that will interact with the agent. You can sign up for a Pokemon Showdown account relatively easily. By choosing a name (top right of website) and then registering that account by clicking on the gear icon (top right of website) and then clicking "register" (3rd option from the top). Then put this username into ```PS_TARGET_USERNAME```.

NOTE: There is a VERY good chance that there may be issues with a newly created account accepting PMs and stuff. If your newly created account does not work, you can login with any of the credentials above and set that as the target username. 

4. **Personalities**: This is just the personality of the agent. You do not need to change this. You can select a new personality directly through the streamlit UI.

## Questions, issues or concerns
Please email me at hcolin0910@gmail.com. Thank you!