import os
from typing import Optional, List, Dict
from model_wrappers.api_gateway import APIGateway

import os
import yaml
from typing import Optional, List, Dict
from pathlib import Path
from model_wrappers.api_gateway import APIGateway

class PokemonTrainerAgent:
    def __init__(self, api_key: Optional[str] = None, max_history: int = 10, personality: str = "npc"):
        print(api_key)
        self.api_key = api_key

        self.max_history = max_history
        self.chat_history: List[Dict[str, str]] = []
        
        # Load personality prompt and append tool usage rules
        base_prompt = self._load_personality_prompt(personality)
        tool_rules = """
        Tool Usage Rules:
            - Tool calls must come BEFORE any response when information lookup is needed
            - Maintain your personality in responses after tool calls
            - Only make tool calls when explicitly relevant to the user's request
            - If unsure about tool use, prompt the user to confirm their intentions

        Battle Manager:
            - When battling is mentioned or challenged, respond with "TOOL: BATTLE_MANAGER"
            - Only call if user clearly intends to battle
            - If battle intentions are unclear, ask user to confirm
            - After the tool call, acknowledge that you will challenge them to a random battle format on Pokemon showdown

        Pokemon Search:
            - When users ask about specific Pokemon, you MUST ONLY respond with "TOOL: POKEMON_SEARCH Pokemon1,Pokemon2,..."
            - NO preliminary text or information about the Pokemon is allowed before or during the tool call
            - Multiple Pokemon should be comma-separated in the tool call
            - Wait for the tool response before providing ANY information about the Pokemon
            - Your response must follow this exact format:
              1. First line: "TOOL: POKEMON_SEARCH PokemonName"
              2. No other text until tool data is received
            - After receiving the data, provide your comprehensive response
            - Act like you already had this information and that it was not provided to you

        Team Builder:
            - When users request team building help, your FIRST line MUST be "TOOL: TEAM_BUILDER <generation> <tier>"
            - NO text is allowed before the TOOL call
            - If either generation or tier is missing, first ask the user to specify it
            - Example format: "TOOL: TEAM_BUILDER gen9 ou"
            - Make no other response before the tool call besides asking for missing information
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
            streaming=False,
            sambanova_api_key=self.api_key
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

    def extract_tool_call(self, response: str) -> tuple[str, Optional[str], Optional[List[str]]]:
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
            
        # For responses starting with "TOOL:", parts[0] will be empty
        # Everything after "TOOL:" needs to be split into tool name and conversation
        tool_and_conversation = parts[1].strip().split("\n", 1)
        
        if len(tool_and_conversation) == 1:
            return "", tool_and_conversation[0].strip()
        
        tool = tool_and_conversation[0].strip()
        conversation = tool_and_conversation[1].strip()
        
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