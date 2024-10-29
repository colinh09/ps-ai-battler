# agent.py
import os
from typing import Optional
from dotenv import load_dotenv
from model_wrappers.api_gateway import APIGateway

class SimpleAgent:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the agent with .env support
        
        Args:
            api_key: Optional API key to override .env file
        """
        # Load environment variables from .env file
        load_dotenv()
        
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv("SAMBANOVA_API_KEY")
        if not self.api_key:
            raise ValueError("SAMBANOVA_API_KEY must be set in .env file or passed to constructor")
        
        # Initialize the LLM
        self.llm = self._init_llm()
        
    def _init_llm(self):
        """Initialize the SambaNova LLM"""
        return APIGateway.load_llm(
            type="sncloud",
            temperature=0.7,
            max_tokens_to_generate=1024,
            select_expert="llama3-70b",
            coe=True,
            do_sample=False,
            sambanova_api_key=self.api_key
        )
    
    def run(self, query: str):
        """Simple query-response interaction"""
        try:
            response = self.llm.invoke(query)
            return response
        except Exception as e:
            return f"Error: {str(e)}"

# Usage example
if __name__ == "__main__":
    # Initialize the agent
    agent = SimpleAgent()
    
    # Run a query
    response = agent.run("Tell me a joke!")
    print(response)