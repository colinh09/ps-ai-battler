# Pokemon Battler, Companion, Rival, Teambuilder
## Overview
This project creates an agent-based chatbot that embodies different Pokemon trainer personalities, focusing on competitive Pokemon battles. The bot handles team building, battles, and strategy discussions using SambaNova Cloud models to generate responses that authentically mimic Pokemon NPCs.

## Project Objective
I have always been fascinated by game-playing AI like Deep Blue, AlphaZero, and OpenAI Five. However, state of the art game-playing AI typically rely on computationally intensive approaches such as deep reinforcement learning. More reasonable approaches such as minimax search or Monte Carlo Tree Search can be viable, but in many cases has already been done for many games, including Pokemon.

With the emergence of RAG-based AI agents and the accessibility of Pokemon Showdown data through web scraping, I saw an opportunity to take a different approach. By leveraging RAG to incorporate competitive Pokemon strategy and game state information, we can create an AI that makes informed decisions without traditional search or learning methods. The interactive nature of LLMs also enables our agent to both play strategically and roleplay as a trainer, creating an immersive battle experience that combines competitive gameplay with personality.

With this in mind, I wanted to accomplish 3 things:
1. Use RAG to help the AI make reasonable battle moves and have informed Pokemon discussions with players
2. Keep response times fast so conversations and battles feel natural, like talking to a real trainer (doable thanks to SambaNova's "lightning fast" inference times)
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

6. Run the application.
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