import os
import asyncio
from dotenv import load_dotenv
from battle_manager import BattleManager
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SystemManager')

class SystemManager:
    """
    High-level manager for Pokemon Showdown bot system.
    Handles user interactions and delegates to appropriate subsystems.
    """
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.battle_manager = None
        self.current_battle = None
        self.is_running = False
        self.logger = logging.getLogger('SystemManager.Main')

    async def start(self):
        """Start the system and begin processing user commands"""
        self.is_running = True
        self.logger.info("Starting system manager")
        
        while self.is_running:
            # Display menu
            print("\n=== Pokemon Showdown Bot ===")
            print("1. Start Battle")
            print("2. Quit")
            
            try:
                choice = input("\nEnter your choice (1-2): ")
                
                if choice == "1":
                    # Get opponent username
                    opponent = input("Enter opponent's username: ")
                    await self.start_battle(opponent)
                elif choice == "2":
                    await self.quit()
                else:
                    print("Invalid choice. Please try again.")
                    
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                print(f"Error: {str(e)}")
                continue

    async def start_battle(self, opponent_username: str):
        """Initialize and start a battle with specified opponent"""
        try:
            while self.is_running:
                self.logger.info(f"Starting battle with {opponent_username}")
                
                self.battle_manager = BattleManager(
                    username=self.username,
                    password=self.password,
                    target_username=opponent_username,
                    db_params=self.get_db_params()
                )
                
                print(f"\nStarting battle with {opponent_username}...")
                await self.battle_manager.start()
                
                print("\n=== Battle Concluded ===")
                print("1. Challenge again")
                print("2. Return to main menu")
                
                choice = input("\nEnter your choice (1-2): ")
                
                if choice == "1":
                    print("Initiating new battle...")
                    continue
                else:
                    print("Returning to main menu...")
                    break
                    
        except Exception as e:
            self.logger.error(f"Failed to start battle: {str(e)}", exc_info=True)
            print(f"Failed to start battle: {str(e)}")
            if self.battle_manager:
                self.battle_manager.is_running = False

    async def quit(self):
        """Cleanup and exit the system"""
        self.logger.info("Shutting down system")
        print("\nShutting down system...")
        if self.battle_manager:
            self.battle_manager.is_running = False
            await asyncio.sleep(1)
            self.battle_manager = None
        self.is_running = False

    def get_db_params(self) -> dict:
        """Get database connection parameters"""
        return {
            'dbname': 'pokemon',
            'user': 'postgres',
            'password': 'password',
            'host': 'localhost',
            'port': '5432'
        }

async def main():
    """Example usage of SystemManager"""
    load_dotenv()
    USERNAME = os.getenv('PS_USERNAME')
    PASSWORD = os.getenv('PS_PASSWORD')
    
    if not USERNAME or not PASSWORD:
        print("Error: Please set PS_USERNAME and PS_PASSWORD environment variables")
        return
    
    system = SystemManager(USERNAME, PASSWORD)
    
    try:
        await system.start()
    except KeyboardInterrupt:
        print("\nSystem stopped by user")
        await system.quit()
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        logger.error(f"Unexpected error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())