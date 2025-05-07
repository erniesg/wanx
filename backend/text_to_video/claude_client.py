from dotenv import load_dotenv
load_dotenv() # Load .env file from workspace root or parent directories

import httpx
import os
import json
from typing import List, Dict, Optional, Any

# It's good practice to load sensitive keys from environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_VERSION = "2023-06-01"  # As per documentation
DEFAULT_MODEL = "claude-3-sonnet-20240229" # A reasonable default, can be overridden
BASE_URL = "https://api.anthropic.com/v1"

class ClaudeAPIError(Exception):
    """Custom exception for Claude API errors."""
    def __init__(self, status_code: int, error_info: Dict):
        self.status_code = status_code
        self.error_type = error_info.get("type")
        self.error_message = error_info.get("message", "Unknown error")
        super().__init__(f"Claude API Error {status_code} ({self.error_type}): {self.error_message}")

class ClaudeClient:
    def __init__(self, api_key: Optional[str] = None, api_version: str = ANTHROPIC_API_VERSION):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("Anthropic API key not found. Please set the ANTHROPIC_API_KEY environment variable or pass it to the client.")
        self.api_version = api_version
        self.base_url = BASE_URL

    async def generate_message(
        self,
        messages: List[Dict[str, Any]],
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        stream: bool = False # Added stream parameter, defaulting to False
    ) -> Dict:
        """
        Sends a request to the Anthropic Messages API.

        Args:
            messages: A list of message objects, e.g., [{"role": "user", "content": "Hello"}].
            model: The model to use (e.g., "claude-3-opus-20240229").
            max_tokens: The maximum number of tokens to generate.
            system_prompt: An optional system prompt.
            temperature: The sampling temperature.
            stream: Whether to stream the response (currently not fully handled for JSON output).

        Returns:
            The JSON response from the API as a dictionary.

        Raises:
            ClaudeAPIError: If the API returns an error.
            httpx.HTTPStatusError: For other HTTP errors.
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if temperature is not None: # API default is 1.0, allow 0.0
            payload["temperature"] = temperature
        if stream: # Though for structured JSON, non-streaming is usually preferred.
            payload["stream"] = True


        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
                response.raise_for_status()  # Raises an HTTPStatusError for 4XX/5XX responses

                # Assuming non-streaming for now for simplicity with JSON output
                # If streaming, the response handling would be different (iterating over events)
                return response.json()

            except httpx.HTTPStatusError as e:
                try:
                    error_data = e.response.json()
                    if "error" in error_data and isinstance(error_data["error"], dict):
                        raise ClaudeAPIError(e.response.status_code, error_data["error"]) from e
                    else: # Fallback if error structure is not as expected
                         raise ClaudeAPIError(e.response.status_code, {"type": "unknown_structure", "message": e.response.text}) from e
                except json.JSONDecodeError: # If the error response itself isn't valid JSON
                    raise ClaudeAPIError(e.response.status_code, {"type": "invalid_error_response", "message": e.response.text}) from e
            except httpx.RequestError as e: # For network errors, timeouts, etc.
                raise ClaudeAPIError(status_code=500, error_info={"type": "network_error", "message": str(e)}) from e


async def main_test():
    """Basic test function to demonstrate client usage."""
    print("Testing Claude Client...")
    try:
        # Ensure ANTHROPIC_API_KEY is set in your environment
        client = ClaudeClient()

        print(f"Using API Key: {client.api_key[:5]}...{client.api_key[-4:] if client.api_key else 'Not Set'}")
        print(f"Using model: {DEFAULT_MODEL}")

        messages_payload = [
            {"role": "user", "content": "Hello, Claude. What are you?"}
        ]
        system_p = "You are a helpful AI assistant."

        print("\n--- Testing Non-Streaming ---")
        response_data = await client.generate_message(
            messages=messages_payload,
            system_prompt=system_p,
            max_tokens=100
        )
        print("Claude's Response (Non-Streaming):")
        # print(json.dumps(response_data, indent=2))
        if response_data.get('content') and isinstance(response_data['content'], list):
            for block in response_data['content']:
                if block.get('type') == 'text':
                    print(block['text'])
        else:
            print(f"Unexpected response structure: {response_data}")


        # Example of how you might try to get JSON (more complex prompt needed for reliable JSON)
        print("\n--- Testing JSON-like request (Illustrative) ---")
        json_messages = [
            {"role": "user", "content": "Tell me a joke in JSON format like: {\"setup\": \"...\", \"punchline\": \"...\"}"}
        ]
        json_system = "You are an AI that always responds in JSON format."

        json_response = await client.generate_message(
            messages=json_messages,
            system_prompt=json_system,
            model="claude-3-haiku-20240307", # Using a faster model for this example
            max_tokens=150,
            temperature=0.2
        )
        print("Claude's JSON Response:")
        # print(json.dumps(json_response, indent=2))
        if json_response.get('content') and isinstance(json_response['content'], list):
            for block in json_response['content']:
                if block.get('type') == 'text':
                    print(block['text']) # The text itself might be a JSON string
                    try:
                        parsed_joke = json.loads(block['text'])
                        print("Parsed JSON joke:", parsed_joke)
                    except json.JSONDecodeError:
                        print("Could not parse the text as JSON.")

        else:
            print(f"Unexpected JSON response structure: {json_response}")


    except ValueError as ve:
        print(f"Configuration Error: {ve}")
    except ClaudeAPIError as cae:
        print(f"Claude API Error: Status {cae.status_code}, Type: {cae.error_type}, Message: {cae.error_message}")
        if hasattr(cae, '__cause__') and cae.__cause__ and hasattr(cae.__cause__, 'response') and cae.__cause__.response:
             print(f"Original response text: {cae.__cause__.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    import asyncio
    # To run the test, you would typically do:
    asyncio.run(main_test())
    # However, since this is a library file, we might not run it directly often.
    # For testing, you can uncomment the line above and run `python claude_client.py`
    # Make sure ANTHROPIC_API_KEY is set in your environment.
    pass
