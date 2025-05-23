import anthropic
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"

class ClaudeClient:
    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables or passed to constructor.")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model

    def generate_structured_output(self, system_prompt: str, user_prompt: str, max_tokens: int = None, temperature: float = None) -> dict | list | None:
        """
        Sends a prompt to Claude and expects a JSON object or list as a response.

        Args:
            system_prompt: The system prompt to guide the AI's behavior and output format.
            user_prompt: The main user query or content to be processed.
            max_tokens: Maximum number of tokens to generate. If None, API default is used.
            temperature: Controls randomness (0.0 to 1.0). If None, API default is used.

        Returns:
            A dictionary or list parsed from Claude's JSON response, or None if an error occurs or parsing fails.
        """
        log_params = {}
        if max_tokens is not None:
            log_params["max_tokens"] = max_tokens
        if temperature is not None:
            log_params["temperature"] = temperature

        logger.info(f"Sending request to Claude model: {self.model} with params: {log_params if log_params else 'API defaults'}")
        # logger.debug(f"System Prompt:\n{system_prompt}")
        # logger.debug(f"User Prompt:\n{user_prompt}")

        try:
            # Construct the API call parameters, only including max_tokens and temperature if they are not None
            api_call_args = {
                "model": self.model,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            }
                        ]
                    }
                ]
            }
            if max_tokens is not None:
                api_call_args["max_tokens"] = max_tokens
            if temperature is not None:
                api_call_args["temperature"] = temperature

            response = self.client.messages.create(**api_call_args)

            # Ensure there is content and it's a TextBlock
            if response.content and isinstance(response.content[0], anthropic.types.TextBlock):
                raw_json_response = response.content[0].text
                logger.debug(f"Claude Raw Response Text:\n{raw_json_response}")

                # The response might sometimes include markdown ```json ... ```, attempt to strip it.
                if raw_json_response.strip().startswith("```json"):
                    raw_json_response = raw_json_response.strip()[7:-3].strip()
                elif raw_json_response.strip().startswith("```"):
                     raw_json_response = raw_json_response.strip()[3:-3].strip()

                try:
                    parsed_response = json.loads(raw_json_response)
                    return parsed_response
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response from Claude: {e}")
                    logger.error(f"Raw response was: {raw_json_response}")
                    return None
            else:
                logger.error("Claude response did not contain expected TextBlock content.")
                logger.error(f"Full response object: {response}")
                return None

        except anthropic.APIConnectionError as e:
            logger.error(f"Claude API connection error: {e.__cause__}")
        except anthropic.RateLimitError as e:
            logger.error(f"Claude API rate limit exceeded: {e.response.text}")
        except anthropic.APIStatusError as e:
            logger.error(f"Claude API status error (status {e.status_code}): {e.response}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while interacting with Claude API: {e}")

        return None

# Example Usage (can be run directly if you have ANTHROPIC_API_KEY set)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing ClaudeClient...")

    try:
        claude_ai = ClaudeClient()

        # Simple test for structured JSON output
        test_system_prompt = "You are a helpful assistant that provides structured data. Respond with a JSON object."
        test_user_prompt = "Give me a JSON object with two keys: 'name' set to 'Test Example' and 'value' set to 123."

        print(f"\n--- Test 1: Simple JSON Object --- ")
        structured_data = claude_ai.generate_structured_output(
            system_prompt=test_system_prompt,
            user_prompt=test_user_prompt,
            max_tokens=100
        )

        if structured_data:
            print("Successfully received and parsed structured data:")
            print(json.dumps(structured_data, indent=2))
            assert isinstance(structured_data, dict)
            assert structured_data.get("name") == "Test Example"
            assert structured_data.get("value") == 123
        else:
            print("Failed to get structured data.")

        # Test for JSON list output
        test_system_prompt_list = "You are a helpful assistant that provides structured data. Respond with a JSON list of strings."
        test_user_prompt_list = "Give me a JSON list containing three fruit names: apple, banana, and cherry."

        print(f"\n--- Test 2: JSON List --- ")
        structured_list = claude_ai.generate_structured_output(
            system_prompt=test_system_prompt_list,
            user_prompt=test_user_prompt_list,
            max_tokens=100
        )

        if structured_list:
            print("Successfully received and parsed structured list:")
            print(json.dumps(structured_list, indent=2))
            assert isinstance(structured_list, list)
            assert "apple" in structured_list
            assert len(structured_list) == 3
        else:
            print("Failed to get structured list.")

    except ValueError as ve:
        print(f"Error during ClaudeClient initialization: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")
