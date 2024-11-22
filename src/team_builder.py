from datetime import datetime, timedelta
import aiohttp
from typing import List, Dict, Tuple, Optional
import re

async def get_stats_urls(generation: str, tier: str) -> tuple[str, str]:
    """Get URLs for usage stats and moveset data from previous month"""
    # Get previous month, handling year transition
    today = datetime.now()
    if today.month == 1:  # If January, go back to December of previous year
        year_month = f"{today.year - 1}-12"
    else:
        # Format month with leading zero
        previous_month = str(today.month - 1).zfill(2)
        year_month = f"{today.year}-{previous_month}"
    
    # Format URLs
    base_url = f"https://www.smogon.com/stats/{year_month}"
    usage_url = f"{base_url}/{generation}{tier}-0.txt"
    moveset_url = f"{base_url}/moveset/{generation}{tier}-0.txt"
    
    return usage_url, moveset_url

async def fetch_data(url: str) -> str:
    print(url)
    """Fetch data from Smogon stats URL"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.text()
            else:
                raise Exception(f"Failed to fetch data from {url}")

def parse_usage_stats(usage_data: str, limit: int = 20) -> Dict[str, float]:
    """Parse usage stats data to get Pokemon rankings and percentages, limited to top N Pokemon"""
    pokemon_stats = {}
    lines = usage_data.split('\n')
    
    # Find the start of the data
    for i, line in enumerate(lines):
        if "| Rank | Pokemon" in line:
            start_index = i + 2  # Skip header row
            break
    
    # Parse Pokemon data
    count = 0
    for line in lines[start_index:]:
        if count >= limit:  # Stop after reaching limit
            break
            
        if '|' not in line or '---' in line:
            break
            
        parts = line.split('|')
        if len(parts) >= 4:
            pokemon_name = parts[2].strip()
            usage_percent = float(parts[3].strip().replace('%', ''))
            pokemon_stats[pokemon_name] = usage_percent
            count += 1
    
    return pokemon_stats

def parse_moveset_data(moveset_data: str, pokemon_name: str) -> Dict:
    """Parse moveset data for a specific Pokemon"""
    # Find the Pokemon's section
    section_start = moveset_data.find(f"| {pokemon_name} ")
    if section_start == -1:
        return None
        
    # Find the end of the section
    section_end = moveset_data.find("\n +----------------------------------------+\n", section_start + 1)
    if section_end == -1:
        section_end = len(moveset_data)
        
    pokemon_section = moveset_data[section_start:section_end]
    
    # Parse each subsection
    data = {
        'abilities': {},
        'items': {},
        'spreads': {},
        'moves': {},
        'teammates': {},
        'counters': {}
    }
    
    current_section = None
    for line in pokemon_section.split('\n'):
        line = line.strip()
        
        # Skip empty lines and dividers
        if not line or line.startswith('+--'):
            continue
            
        # Check for section headers
        if line.endswith('|'):
            section = line.strip('| ').lower()
            if section in ['abilities', 'items', 'spreads', 'moves', 'teammates', 'checks and counters']:
                current_section = section
                continue
        
        # Parse data lines
        if current_section and '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                name = parts[0]
                # Extract percentage from the data
                if '%' in parts[1]:
                    percentage = float(parts[1].split('%')[0])
                    if current_section == 'checks and counters':
                        data['counters'][name] = percentage
                    elif current_section == 'teammates':
                        data['teammates'][name] = percentage
                    else:
                        data[current_section][name] = percentage
    
    return data

def extract_from_response(response: str) -> Tuple[str, str, str]:
    """Extract pokemon name, reasoning, and set from agent's response"""
    print("FULL RESPONSE:", response)  # Print the whole response
    
    name_match = re.search(r"SELECTED_POKEMON: (.+?)(?:\n|$)", response)
    print("NAME MATCH:", name_match)  # Print if we found a name
    pokemon_name = name_match.group(1).strip() if name_match else None
    
    reasoning_match = re.search(r"REASONING: (.+?)(?=SET:|$)", response, re.DOTALL)
    print("REASONING MATCH:", reasoning_match)  # Print if we found reasoning
    reasoning = reasoning_match.group(1).strip() if reasoning_match else None
    
    set_match = re.search(r"SET:\n([\s\S]+?)(?:\n\n|$)", response)
    print("SET MATCH:", set_match)  # Print if we found a set
    set_text = set_match.group(1).strip() if set_match else None

    return pokemon_name, reasoning, set_text

async def build_team(bot, agent, target_username, generation, tier) -> List[str]:
    """
    Main team building function that returns the complete team sets
    Returns:
        List[str]: List of Pokemon sets in Showdown format
    """
    try:
        # Get and fetch data
        usage_url, moveset_url = await get_stats_urls(generation, tier)
        usage_data = await fetch_data(usage_url)
        moveset_data = await fetch_data(moveset_url)
        
        # Parse usage stats
        usage_stats = parse_usage_stats(usage_data, limit=20)
        
        # Initialize team building
        team_sets = []
        team_context = []
        
        await bot.send_pm(target_username, f"I'll build a {generation} {tier} team. I'll explain my choices as I go...")
        
        for i in range(6):
            if i == 0:
                prompt = f"""You are building a {generation} {tier} team. Here are the usage statistics:
                {usage_stats}
                
                Select a Pokemon to build around (preferably with >10% usage but not always the highest).
                
                Format your response exactly like this:
                SELECTED_POKEMON: <pokemon name>
                
                REASONING: <explain your choice, considering usage stats and the Pokemon's role>
                
                SET:
                <pokemon name> @ <item>
                Ability: <ability>
                Tera Type: <tera type>
                EVs: <ev spread>
                <nature> Nature
                - <move 1>
                - <move 2>
                - <move 3>
                - <move 4>
                """
            else:
                prompt = f"""Current team:
                {team_sets}
                
                Team context (movesets, teammates, counters):
                {team_context}
                
                Select the next Pokemon for the team based on our needs and synergy.
                
                Format your response exactly like this:
                SELECTED_POKEMON: <pokemon name>
                
                REASONING: <explain your choice, considering team needs, synergy, and coverage>
                
                SET:
                <pokemon name> @ <item>
                Ability: <ability>
                Tera Type: <tera type>
                EVs: <ev spread>
                <nature> Nature
                - <move 1>
                - <move 2>
                - <move 3>
                - <move 4>
                """
            
            # Get agent's response
            response = agent.run(prompt)
            
            # Extract components
            pokemon_name, reasoning, set_text = extract_from_response(response)
            
            if not all([pokemon_name, reasoning, set_text]):
                raise ValueError("Failed to parse agent's response properly")
            
            # Get moveset data for context
            pokemon_data = parse_moveset_data(moveset_data, pokemon_name)
            team_context.append(pokemon_data)
            team_sets.append(set_text)
            
            # Send only the reasoning to the user
            await bot.send_pm(target_username, f"Pokemon #{i+1} - {pokemon_name}:\n{reasoning}")
        
        # Return the complete team sets
        return team_sets
        
    except Exception as e:
        await bot.send_pm(target_username, f"I encountered an error while building the team: {str(e)}")
        return []