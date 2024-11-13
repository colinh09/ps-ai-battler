import os
from typing import Optional
from dotenv import load_dotenv
from model_wrappers.api_gateway import APIGateway

class PokemonTrainerAgent:
    def __init__(self, api_key: Optional[str] = None):
        # Load environment variables from .env file
        load_dotenv()
        
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv("SAMBANOVA_API_KEY")
        if not self.api_key:
            raise ValueError("SAMBANOVA_API_KEY must be set in .env file or passed to constructor")
        
        # System prompt that defines the agent's personality
        self.system_prompt = """You are a friendly and knowledgeable Pokemon trainer..."""
        
        # Initialize the Chat LLM
        self.llm = self._init_llm()
    
    def _init_llm(self):
        """Initialize the SambaNova Chat LLM"""
        return APIGateway.load_chat(
            type="sncloud",
            model="llama3-70b",  # or whatever model you're using
            temperature=0.7,
            max_tokens=1024,
            streaming=False
        )
    
    def run(self, query: str) -> str:
        """Process user input and generate appropriate response"""
        try:
            # Create message list with system and user messages
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": query}
            ]
            
            # Get response from LLM
            response = self.llm.invoke(messages)
            return response.content  # Chat models usually return a message object
            
        except Exception as e:
            return f"Error: {str(e)}"