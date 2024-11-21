import os
import asyncio
from dotenv import load_dotenv
from battle_manager import BattleManager
from agents.converse_agent import PokemonTrainerAgent
from ps_bot.ps_client import ShowdownBot
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
    def __init__(self, username: str, password: str, target_username: str, personality: str = "npc"):
        self.username = username
        self.password = password
        self.target_username = target_username
        self.is_running = False
        self.logger = logging.getLogger('SystemManager.Main')
        
        # Initialize the ShowdownBot directly (no longer in battle_manager)
        self.bot = ShowdownBot(username, password, target_username)
        
        # Initialize the conversational agent
        self.agent = PokemonTrainerAgent(personality=personality)
        self.personality = personality
        
        # Battle manager will be created only when needed
        self.battle_manager = None
        self.current_battle = None

    async def start(self):
        """Start the system and begin processing messages"""
        self.is_running = True
        self.logger.info("Starting system manager")
        
        # Connect to Pokemon Showdown
        await self.bot.connect()
        
        print("\nConnected to Pokemon Showdown! Ready to receive messages.")
        
        while self.is_running:
            try:
                # Get user input from Pokemon Showdown
                message = await self.bot.ws.recv()
                
                if "|pm|" in message:
                    parts = message.split("|")
                    if len(parts) >= 5:
                        sender = parts[2].strip()
                        content = parts[4]
                        
                        # Only process PMs from our target user that aren't system messages about challenges
                        if (sender.lower().strip() == self.target_username.lower().strip() and 
                            "rejected the challenge" not in content and "accepted the challenge" not in content
                            and content != "/challenge"):
                            print(content)
                            # Get agent's response
                            response = self.agent.run(content)
                            conversation, tool = self.agent.extract_tool_call(response)
                            
                            # Send the conversational response back as PM
                            if conversation:
                                await self.bot.send_pm(sender, conversation)
                            
                            # Handle tool calls
                            if tool == "BATTLE_MANAGER":
                                await self.start_battle(sender)
                
                elif "|challstr|" in message:
                    challstr = message.split("|challstr|")[1]
                    await self.bot.login(challstr, True)
            
            except KeyboardInterrupt:
                await self.quit()
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                print(f"Error: {str(e)}")
                continue

    async def start_battle(self, opponent_username: str):
        """Initialize and start a battle with specified opponent"""
        try:
            self.logger.info(f"Starting battle with {opponent_username}")
            
            # Create battle manager if it doesn't exist or create new one if needed
            if not self.battle_manager or not self.battle_manager.is_running:
                self.battle_manager = BattleManager(
                    username=self.username,
                    password=self.password,
                    target_username=opponent_username,
                    db_params=self.get_db_params(),
                    personality=self.personality
                )
                self.battle_manager.system_manager = self
                
            # Initialize battle loop
            print(f"\nConnecting to Pokemon Showdown for battle...")
            try:
                await self.battle_manager.bot.connect()
                print("Connected successfully!")
                
                # Initialize battle loop
                self.battle_manager.is_running = True
                self.battle_manager.battle_concluded = False
                
                # Start the message receiving task
                receive_task = asyncio.create_task(self.battle_manager.bot.receive_messages())
                battle_task = asyncio.create_task(self.battle_manager.run_battle_loop())
                
                # Wait for both tasks to complete
                print("Starting battle tasks...")
                try:
                    await asyncio.gather(receive_task, battle_task)
                except asyncio.CancelledError:
                    pass
                
                # After battle ends, send analysis
                await self.battle_manager.bot.send_pm(
                    opponent_username, 
                    "Analyzing battle results..."
                )
                
                # Get final state and history
                final_state = self.battle_manager.current_state
                battle_history = self.battle_manager.bot.get_battle_history_text()
                
                # Generate and send analysis
                if final_state and battle_history:
                    analysis = self.battle_manager.agent.run(
                        f"""Analyze this completed Pokemon battle. Review the battle history and final state to provide insights.

                        Battle History:
                        {battle_history}

                        Final Battle State:
                        {self.battle_manager.parse_battle_state(final_state)}

                        Please provide:
                        1. An overview of how the battle progressed
                        2. Key turning points or critical moments
                        3. Effective strategies that were used
                        4. Areas for improvement
                        5. Notable matchups and how they influenced the battle
                        
                        Focus on constructive analysis that could help improve future battles. Use paragraphs with no headers."""
                    )
                    
                    if analysis:
                        await self.battle_manager.bot.send_pm(opponent_username, analysis)
                    
            except Exception as e:
                print(f"Error in battle setup: {str(e)}")
                self.logger.error(f"Battle setup failed: {str(e)}", exc_info=True)
                raise
                
        except Exception as e:
            self.logger.error(f"Failed to start battle: {str(e)}", exc_info=True)
            print(f"Failed to start battle: {str(e)}")
            if self.battle_manager:
                self.battle_manager.is_running = False
            raise
                
    async def forfeit_battle(self) -> bool:
        """Forfeit the current battle if one is active"""
        try:
            if not self.battle_manager or not self.battle_manager.is_running:
                print("No active battle to forfeit")
                return False
                
            success = await self.battle_manager.forfeit()
            if success:
                print("Successfully forfeited the battle")
            else:
                print("Failed to forfeit the battle")
            return success
        except Exception as e:
            self.logger.error(f"Error in forfeit_battle: {str(e)}")
            print(f"Error forfeiting battle: {str(e)}")
            return False

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
    
    # Get credentials and target user from environment variables
    USERNAME = os.getenv('PS_USERNAME')
    PASSWORD = os.getenv('PS_PASSWORD')
    TARGET_USERNAME = os.getenv('PS_TARGET_USERNAME')
    
    if not all([USERNAME, PASSWORD, TARGET_USERNAME]):
        print("Error: Please set PS_USERNAME, PS_PASSWORD, and PS_TARGET_USERNAME environment variables")
        return
    
    system = SystemManager(USERNAME, PASSWORD, TARGET_USERNAME, personality="arrogant_rival")
    
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