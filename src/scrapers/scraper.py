from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import json
import os

def create_data_directory():
    if not os.path.exists('data'):
        os.makedirs('data')

def scrape_smogon_abilities():
    driver = webdriver.Chrome()
    driver.get("https://www.smogon.com/dex/sv/abilities/")
    
    abilities_data = []
    processed_abilities = set()
    
    def extract_ability_data(ability_row):
        try:
            name = ability_row.find_element(By.CLASS_NAME, "AbilityRow-name").text.strip()
            
            if name in processed_abilities:
                return None
                
            description = ability_row.find_element(By.CLASS_NAME, "AbilityRow-description").text.strip()
            
            processed_abilities.add(name)
            
            return {
                "name": name,
                "description": description
            }
        except Exception as e:
            return None

    current_scroll = 0
    scroll_amount = 36.8  # Using same scroll amount as other scrapers
    no_new_abilities_count = 0
    
    while True:
        try:
            ability_rows = driver.find_elements(By.CLASS_NAME, "AbilityRow")
            abilities_before = len(abilities_data)
            
            for row in ability_rows:
                ability_info = extract_ability_data(row)
                if ability_info:
                    abilities_data.append(ability_info)
                    print(f"Processed: {ability_info['name']} ({len(abilities_data)} abilities total)")
                    
                    current_scroll += scroll_amount
                    driver.execute_script(f"window.scrollTo(0, {current_scroll})")
                    time.sleep(0.5)
            
            if len(abilities_data) == abilities_before:
                no_new_abilities_count += 1
            else:
                no_new_abilities_count = 0
            
            if no_new_abilities_count >= 5:
                print("\nNo new abilities found. Finishing scraping...")
                break
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    driver.quit()
    
    unique_abilities = {ability['name']: ability for ability in abilities_data}.values()
    abilities_data = sorted(list(unique_abilities), key=lambda x: x['name'])
    
    create_data_directory()
    df = pd.DataFrame(abilities_data)
    df.to_csv('data/smogon_abilities.csv', index=False)
    
    with open('data/smogon_abilities.json', 'w') as f:
        json.dump(abilities_data, f, indent=2)
    
    print(f"\nScraping completed!")
    print(f"Total unique abilities scraped: {len(abilities_data)}")
    return abilities_data

def scrape_smogon_pokemon():
    driver = webdriver.Chrome()
    driver.get("https://www.smogon.com/dex/sv/pokemon/")
    
    pokemon_data = []
    processed_pokemon = set()
    
    def extract_pokemon_data(pokemon_row):
        try:
            name = pokemon_row.find_element(By.CLASS_NAME, "PokemonAltRow-name").text.strip()
            
            if name in processed_pokemon:
                return None
                
            # Get types - explicitly handle type1 and type2
            types_element = pokemon_row.find_element(By.CLASS_NAME, "PokemonAltRow-types")
            type_elements = types_element.find_elements(By.CLASS_NAME, "TypeList")
            type1 = type_elements[0].text.strip() if len(type_elements) > 0 else None
            type2 = type_elements[1].text.strip() if len(type_elements) > 1 else None
            
            # Get abilities - explicitly handle ability1, ability2, and ability3
            abilities_elements = pokemon_row.find_elements(By.CLASS_NAME, "PokemonAltRow-abilities")
            all_abilities = []
            for ability_list in abilities_elements:
                ability_items = ability_list.find_elements(By.TAG_NAME, "li")
                all_abilities.extend([item.text.strip() for item in ability_items])
            
            ability1 = all_abilities[0] if len(all_abilities) > 0 else None
            ability2 = all_abilities[1] if len(all_abilities) > 1 else None
            ability3 = all_abilities[2] if len(all_abilities) > 2 else None
            
            # Get formats/tiers
            formats_element = pokemon_row.find_element(By.CLASS_NAME, "PokemonAltRow-tags")
            formats = [format_elem.text.strip() for format_elem in formats_element.find_elements(By.TAG_NAME, "li")]
            
            # Get stats
            stats = {}
            stat_types = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']
            for stat in stat_types:
                try:
                    stat_value = pokemon_row.find_element(By.CLASS_NAME, f"PokemonAltRow-{stat}").text.strip()
                    stats[stat] = stat_value
                except:
                    stats[stat] = None
            
            processed_pokemon.add(name)
            
            return {
                "name": name,
                "type1": type1,
                "type2": type2,
                "ability1": ability1,
                "ability2": ability2,
                "ability3": ability3,
                "formats": formats,
                "hp": stats['hp'],
                "atk": stats['atk'],
                "def": stats['def'],
                "spa": stats['spa'],
                "spd": stats['spd'],
                "spe": stats['spe']
            }
        except Exception as e:
            print(f"Error processing Pokemon: {e}")
            return None

    current_scroll = 0
    scroll_amount = 36.8
    no_new_pokemon_count = 0
    
    while True:
        try:
            pokemon_rows = driver.find_elements(By.CLASS_NAME, "PokemonAltRow")
            pokemon_before = len(pokemon_data)
            
            for row in pokemon_rows:
                pokemon_info = extract_pokemon_data(row)
                if pokemon_info:
                    pokemon_data.append(pokemon_info)
                    print(f"Processed: {pokemon_info['name']} ({len(pokemon_data)} Pokemon total)")
                    
                    current_scroll += scroll_amount
                    driver.execute_script(f"window.scrollTo(0, {current_scroll})")
                    time.sleep(0.5)
            
            if len(pokemon_data) == pokemon_before:
                no_new_pokemon_count += 1
            else:
                no_new_pokemon_count = 0
            
            if no_new_pokemon_count >= 5:
                print("\nNo new Pokemon found. Finishing scraping...")
                break
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    driver.quit()
    
    unique_pokemon = {pokemon['name']: pokemon for pokemon in pokemon_data}.values()
    pokemon_data = sorted(list(unique_pokemon), key=lambda x: x['name'])
    
    create_data_directory()
    df = pd.DataFrame(pokemon_data)
    df.to_csv('data/smogon_pokemon.csv', index=False)
    
    with open('data/smogon_pokemon.json', 'w') as f:
        json.dump(pokemon_data, f, indent=2)
    
    print(f"\nScraping completed!")
    print(f"Total unique Pokemon scraped: {len(pokemon_data)}")
    return pokemon_data

def scrape_smogon_moves():
    driver = webdriver.Chrome()
    driver.get("https://www.smogon.com/dex/sv/moves/")
    
    moves_data = []
    processed_moves = set()
    
    def extract_move_data(move_row):
        try:
            name = move_row.find_element(By.CLASS_NAME, "MoveRow-name").text.strip()
            
            if name in processed_moves:
                return None
                
            move_type = move_row.find_element(By.CLASS_NAME, "MoveRow-type").text.strip()
            power_value = move_row.find_element(By.CLASS_NAME, "MoveRow-power").find_element(By.TAG_NAME, "span").text.strip()
            accuracy_value = move_row.find_element(By.CLASS_NAME, "MoveRow-accuracy").find_element(By.TAG_NAME, "span").text.strip()
            pp_value = move_row.find_element(By.CLASS_NAME, "MoveRow-pp").find_element(By.TAG_NAME, "span").text.strip()
            description = move_row.find_element(By.CLASS_NAME, "MoveRow-description").text.strip()
            
            processed_moves.add(name)
            
            return {
                "name": name,
                "type": move_type,
                "power": power_value,
                "accuracy": accuracy_value,
                "pp": pp_value,
                "description": description
            }
        except Exception as e:
            return None

    current_scroll = 0
    scroll_amount = 36.8
    no_new_moves_count = 0
    
    while True:
        try:
            move_rows = driver.find_elements(By.CLASS_NAME, "MoveRow")
            moves_before = len(moves_data)
            
            for row in move_rows:
                move_data = extract_move_data(row)
                if move_data:
                    moves_data.append(move_data)
                    print(f"Processed: {move_data['name']} ({len(moves_data)} moves total)")
                    
                    current_scroll += scroll_amount
                    driver.execute_script(f"window.scrollTo(0, {current_scroll})")
                    time.sleep(0.5)
            
            if len(moves_data) == moves_before:
                no_new_moves_count += 1
            else:
                no_new_moves_count = 0
            
            if no_new_moves_count >= 5:
                print("\nNo new moves found. Finishing scraping...")
                break
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    driver.quit()
    
    unique_moves = {move['name']: move for move in moves_data}.values()
    moves_data = sorted(list(unique_moves), key=lambda x: x['name'])
    
    create_data_directory()
    df = pd.DataFrame(moves_data)
    df.to_csv('data/smogon_moves.csv', index=False)
    
    with open('data/smogon_moves.json', 'w') as f:
        json.dump(moves_data, f, indent=2)
    
    print(f"\nScraping completed!")
    print(f"Total unique moves scraped: {len(moves_data)}")
    return moves_data

def scrape_smogon_items():
    driver = webdriver.Chrome()
    driver.get("https://www.smogon.com/dex/sv/items/")
    
    items_data = []
    processed_items = set()
    
    def extract_item_data(item_row):
        try:
            name = item_row.find_element(By.CLASS_NAME, "ItemRow-name").text.strip()
            
            if name in processed_items:
                return None
                
            description = item_row.find_element(By.CLASS_NAME, "ItemRow-description").text.strip()
            
            processed_items.add(name)
            
            return {
                "name": name,
                "description": description
            }
        except Exception as e:
            return None

    current_scroll = 0
    scroll_amount = 36.8
    no_new_items_count = 0
    
    while True:
        try:
            item_rows = driver.find_elements(By.CLASS_NAME, "ItemRow")
            items_before = len(items_data)
            
            for row in item_rows:
                item_info = extract_item_data(row)
                if item_info:
                    items_data.append(item_info)
                    print(f"Processed: {item_info['name']} ({len(items_data)} items total)")
                    
                    current_scroll += scroll_amount
                    driver.execute_script(f"window.scrollTo(0, {current_scroll})")
                    time.sleep(0.5)
            
            if len(items_data) == items_before:
                no_new_items_count += 1
            else:
                no_new_items_count = 0
            
            if no_new_items_count >= 5:
                print("\nNo new items found. Finishing scraping...")
                break
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    driver.quit()
    
    unique_items = {item['name']: item for item in items_data}.values()
    items_data = sorted(list(unique_items), key=lambda x: x['name'])
    
    create_data_directory()
    df = pd.DataFrame(items_data)
    df.to_csv('data/smogon_items.csv', index=False)
    
    with open('data/smogon_items.json', 'w') as f:
        json.dump(items_data, f, indent=2)
    
    print(f"\nScraping completed!")
    print(f"Total unique items scraped: {len(items_data)}")
    return items_data

def main():
    while True:
        print("\nWhat would you like to scrape?")
        print("1. Moves")
        print("2. Pokemon")
        print("3. Abilities")
        print("4. Items")
        print("5. Exit")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == "1":
            moves = scrape_smogon_moves()
        elif choice == "2":
            pokemon = scrape_smogon_pokemon()
        elif choice == "3":
            abilities = scrape_smogon_abilities()
        elif choice == "4":
            items = scrape_smogon_items()
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()