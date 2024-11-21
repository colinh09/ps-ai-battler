import os
from typing import Optional, List, Dict
from dotenv import load_dotenv
from model_wrappers.api_gateway import APIGateway

import os
import yaml
from typing import Optional, List, Dict
from pathlib import Path
from dotenv import load_dotenv
from model_wrappers.api_gateway import APIGateway

class PokemonTrainerAgent:
    def __init__(self, api_key: Optional[str] = None, max_history: int = 10, personality: str = "npc"):
        load_dotenv()
        
        self.api_key = api_key or os.getenv("SAMBANOVA_API_KEY")
        if not self.api_key:
            raise ValueError("SAMBANOVA_API_KEY must be set in .env file or passed to constructor")

        self.max_history = max_history
        self.chat_history: List[Dict[str, str]] = []
        
        # Load personality prompt and append tool usage rules
        base_prompt = self._load_personality_prompt(personality)
        tool_rules = """
        
    Tool Usage Rules:
    - Always provide your character response before any tool calls
    - When battling is mentioned or challenged, end your response with "TOOL: BATTLE_MANAGER"
    - Tool calls must come after your complete response, never in the middle
    - Maintain your personality even when calling tools
    """
        self.system_prompt = base_prompt + tool_rules
        
        self.llm = self._init_llm()

    
    def _load_personality_prompt(self, personality: str) -> str:
        current_dir = Path(__file__).parent
        prompts_dir = current_dir.parent / "prompts"
        prompt_path = prompts_dir / f"{personality}.yaml"
        
        try:
            with open(prompt_path, "r") as f:
                prompt_data = yaml.safe_load(f)
                return prompt_data["system_prompt"]
        except FileNotFoundError:
            raise ValueError(f"Personality file not found: {prompt_path}")
        except KeyError:
            raise ValueError(f"Invalid personality file format: {prompt_path}")

    
    def _init_llm(self):
        """Initialize the SambaNova Chat LLM"""
        return APIGateway.load_chat(
            type="sncloud",
            model="llama3-70b",
            temperature=0.7,
            max_tokens=1024,
            streaming=False
        )
    
    def get_messages_with_history(self, new_message: str) -> List[Dict[str, str]]:
        """
        Combine system prompt, chat history, and new message
        
        Args:
            new_message: Latest user message
            
        Returns:
            List of messages including system prompt, history, and new message
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add chat history
        messages.extend(self.chat_history[-self.max_history:])
        
        # Add new user message
        messages.append({"role": "user", "content": new_message})
        
        return messages
    
    def add_to_history(self, role: str, content: str):
        """
        Add a message to chat history
        
        Args:
            role: Message role ("user" or "assistant")
            content: Message content
        """
        self.chat_history.append({"role": role, "content": content})
        
        # Trim history if it exceeds max length
        # if len(self.chat_history) > self.max_history:
        #     self.chat_history = self.chat_history[-self.max_history:]
    
    def run(self, query: str) -> str:
        """
        Process user input and generate appropriate response
        
        Args:
            query: User's input message
            
        Returns:
            str: Agent's response, potentially including tool markers
        """
        try:
            # Get messages with history
            messages = self.get_messages_with_history(query)
            
            # Add user message to history
            self.add_to_history("user", query)
            
            # Get response from LLM
            response = self.llm.invoke(messages)
            response_content = response.content
            
            # Add assistant response to history
            self.add_to_history("assistant", response_content)
            
            return response_content
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def clear_history(self):
        """Clear the chat history"""
        self.chat_history = []

    def extract_tool_call(self, response: str) -> tuple[str, Optional[str]]:
        """
        Extract any tool calls from the response
        
        Args:
            response: Raw response from LLM
            
        Returns:
            tuple[str, Optional[str]]: (conversation_text, tool_name if any)
        """
        parts = response.split("TOOL:", 1)
        
        if len(parts) == 1:
            return response.strip(), None
            
        conversation = parts[0].strip()
        tool = parts[1].strip()
        
        return conversation, tool

# Usage example
if __name__ == "__main__":
    # Initialize the agent
    agent = PokemonTrainerAgent(max_history=10)
    
    # Example conversation
    responses = [
        agent.run("Hi! I'm a new Pokemon trainer!"),
        agent.run("Can you tell me about Dragapult?"),
        agent.run("That sounds cool! Want to battle?")
    ]
    
    # Print responses
    for i, response in enumerate(responses, 1):
        print(f"\nInteraction {i}:")
        conversation, tool = agent.extract_tool_call(response)
        print("Response:", conversation)
        if tool:
            print("Tool Called:", tool)