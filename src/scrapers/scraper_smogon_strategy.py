import psycopg2
import json
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def connect_to_db(db_params):
    """Establish connection to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**db_params)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def get_pokemon_names(conn):
    """Fetch all Pokemon names from database"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT pokemon_name FROM pokemon")
        pokemon_names = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return pokemon_names
    except psycopg2.Error as e:
        print(f"Error fetching Pokemon names: {e}")
        return []

def setup_selenium():
    """Configure and initialize Selenium WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=chrome_options)

def check_page_exists(driver):
    """Check if page exists or shows error message"""
    try:
        error_text = driver.find_element(By.XPATH, "//p[contains(text(), 'Try again from the')]")
        return False
    except NoSuchElementException:
        return True

def is_outdated_content(text):
    """Check if the content contains the outdated analysis disclaimer"""
    outdated_marker = "This set / analysis was uploaded before the May tier shift"
    return outdated_marker in text

def get_strategy_content(driver):
    """Extract strategy content specifically"""
    try:
        # First check for the Strategies header
        try:
            strategy_header = driver.find_element(By.XPATH, "//h2[text()='Strategies']")
        except NoSuchElementException:
            print("  → Status: No Strategies section found")
            return "no content"

        # Check for "No movesets available" message
        try:
            no_movesets = driver.find_element(By.XPATH, "//span[contains(text(), 'No movesets available')]")
            print("  → Status: No movesets available message found")
            return "no content"
        except NoSuchElementException:
            pass

        # Look for paragraphs under strategy sections
        strategy_paragraphs = driver.find_elements(By.XPATH, "//section//p[string-length(text()) > 0]")
        
        if not strategy_paragraphs:
            print("  → Status: No strategy paragraphs found")
            return "no content"

        # Filter out outdated content and combine remaining paragraphs
        valid_paragraphs = []
        for p in strategy_paragraphs:
            text = p.text.strip()
            if text and not is_outdated_content(text):
                valid_paragraphs.append(text)

        if not valid_paragraphs:
            print("  → Status: Only outdated content found")
            return "outdated"
        
        text = " ".join(valid_paragraphs)
        print(f"  → Status: Successfully found {len(valid_paragraphs)} valid strategy paragraph(s)")
        return text

    except Exception as e:
        print(f"  → Status: Error extracting strategy content - {str(e)}")
        return "error"

def scrape_pokemon_data(driver, pokemon_name):
    """Scrape Pokemon strategy data from Smogon website"""
    url = f"https://www.smogon.com/dex/sv/pokemon/{pokemon_name.lower()}"
    try:
        driver.get(url)
        # Wait for content to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)  # Allow for dynamic content to load
        
        # Check if page exists
        if not check_page_exists(driver):
            print(f"  → Status: Page not found")
            return "not found"
            
        # Get strategy content
        return get_strategy_content(driver)
        
    except TimeoutException:
        print(f"  → Status: Page load timeout")
        return "not found"
    except Exception as e:
        print(f"  → Status: Error - {str(e)}")
        return "error"

def main():
    # Database connection parameters
    db_params = {
        'dbname': 'pokemon',
        'user': 'postgres',
        'password': 'password',
        'host': 'localhost',
        'port': '5432'
    }
    
    # Create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
        print("Created 'data' directory")
    
    # Connect to database
    print("Connecting to database...")
    conn = connect_to_db(db_params)
    if not conn:
        return
    
    # Get Pokemon names
    print("Fetching Pokemon names from database...")
    pokemon_names = get_pokemon_names(conn)
    conn.close()
    print(f"Found {len(pokemon_names)} Pokemon in database")
    
    # Initialize WebDriver
    print("Initializing Selenium WebDriver...")
    driver = setup_selenium()
    
    # Dictionary to store results
    pokemon_data = {}
    
    try:
        # Process each Pokemon
        print("\nStarting data collection:")
        print("------------------------")
        for i, pokemon_name in enumerate(pokemon_names, 1):
            print(f"\nProcessing {pokemon_name} ({i}/{len(pokemon_names)})...")
            text_content = scrape_pokemon_data(driver, pokemon_name)
            pokemon_data[pokemon_name] = {
                "name": pokemon_name,
                "text": text_content
            }
        
        # Save results to JSON file
        output_path = 'data/pokemon_descriptions.json'
        print(f"\nSaving results to {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(pokemon_data, f, ensure_ascii=False, indent=2)
            
    finally:
        driver.quit()
    
    print("\nData collection complete!")
    print(f"Results saved to {output_path}")
    
    # Print summary
    print("\nSummary:")
    print("--------")
    total = len(pokemon_data)
    not_found = sum(1 for item in pokemon_data.values() if item['text'] == 'not found')
    no_content = sum(1 for item in pokemon_data.values() if item['text'] == 'no content')
    outdated = sum(1 for item in pokemon_data.values() if item['text'] == 'outdated')
    error_count = sum(1 for item in pokemon_data.values() if item['text'] == 'error')
    success = total - not_found - no_content - outdated - error_count
    print(f"Total Pokemon processed: {total}")
    print(f"Successfully scraped: {success}")
    print(f"Pages not found: {not_found}")
    print(f"Pages with no content: {no_content}")
    print(f"Pages with only outdated content: {outdated}")
    print(f"Errors during scraping: {error_count}")

if __name__ == "__main__":
    main()