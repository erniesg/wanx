from groq import Groq
import os
import json
import asyncio # Add asyncio for async operations
from typing import Optional # Import Optional

# Import Claude client and related items
from .claude_client import ClaudeClient, ClaudeAPIError, DEFAULT_MODEL as DEFAULT_CLAUDE_MODEL

def remove_think_tags(text):
    """
    Removes content enclosed in <think> tags from the text.

    Args:
        text (str): The input text containing <think> tags

    Returns:
        str: Text with the <think> sections removed
    """
    import re

    # Pattern to match <think> tags and their content
    pattern = r'<think>.*?</think>\s*'

    # Remove the matched pattern using regex
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)

    # Return the cleaned text
    return cleaned_text.strip()

def transform_to_script(input_text, temperature=0.6, max_tokens=9000, top_p=0.95):
    """
    Transform any text into a script format using Groq's AI model.

    Args:
        input_text (str): The text to transform into a script
        temperature (float): Controls randomness (0.0-1.0)
        max_tokens (int): Maximum number of tokens to generate
        top_p (float): Controls diversity via nucleus sampling

    Returns:
        str: The generated script
    """
    client = Groq()

    system_prompt = f"""You are an amazing youtube shorts and tiktok creator you have been given a news piece you want to make that into a youtube short"""

    try:
        completion = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"Transform this text #Content {input_text} and transform that into a short form content for tiktok and youtube shorts of about 15 seconds in duration, around 200 characters, in complete sentences, we just want the content that the human should read. only give the text that i should be reading. no hashtags at the end"
                }
            ],
            temperature=temperature,
            top_p=top_p,
            stream=True,
            stop=None,
        )

        # For returning the complete text
        full_response = ""

        # Print the response as it streams
        print(f"Transforming text into youtube shorts script...\n")
        for chunk in completion:
            content = chunk.choices[0].delta.content or ""
            print(content, end="")
            full_response += content

        cleaned_response = remove_think_tags(full_response)

        return cleaned_response

    except Exception as e:
        print(f"Error transforming text: {e}")
        return None

async def transform_to_tech_in_asia_script(
    input_text: str,
    llm_provider: str = "groq", # "groq" or "claude"
    model_name: Optional[str] = None,
    temperature: float = 0.6,
    max_tokens: int = 9000, # Groq default
    top_p: float = 0.95
):
    """
    Transform any text into a Tech in Asia style video script using the specified LLM provider,
    expecting a JSON output.

    Args:
        input_text (str): The text to transform into a script.
        llm_provider (str): The LLM provider to use ("groq" or "claude").
        model_name (Optional[str]): Specific model name for the provider.
                                     Defaults to Groq's or Claude's default if None.
        temperature (float): Controls randomness (0.0-1.0).
        max_tokens (int): Maximum number of tokens to generate.
        top_p (float): Controls diversity via nucleus sampling (Groq only).

    Returns:
        dict: The generated script as a Python dictionary, or None if an error occurs.
    """

    # Determine the path to the prompt file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file_path = os.path.join(current_dir, "..", "..", "config", "tech_in_asia_script_prompt.md")

    try:
        with open(prompt_file_path, "r") as f:
            system_prompt_content_template = f.read() # This is the system prompt for the LLM
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {prompt_file_path}")
        return None
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        return None

    # The user content remains the same, asking for JSON output based on the system prompt's <output_format>
    user_content_for_llm = f"{input_text}\\n\\nEnsure the output is a valid JSON object adhering to the specified <output_format> in the system prompt."

    raw_response_text = None

    if llm_provider == "groq":
        client = Groq()
        actual_model_name = model_name or "deepseek-r1-distill-llama-70b" # Groq default
        print(f"\n--- Using Groq LLM ({actual_model_name}) ---")
        try:
            completion = client.chat.completions.create(
                model=actual_model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt_content_template
                    },
                    {
                        "role": "user",
                        "content": user_content_for_llm
                    }
                ],
                temperature=temperature,
                top_p=top_p,
                stream=False,
                stop=None,
            )
            raw_response_text = completion.choices[0].message.content
        except Exception as e:
            print(f"Error transforming text with Groq: {e}")
            return None

    elif llm_provider == "claude":
        claude_client = ClaudeClient() # API key loaded from env
        actual_model_name = model_name or DEFAULT_CLAUDE_MODEL
        # Claude uses 'max_tokens' slightly differently, let's cap it for safety if not specified for Claude
        claude_max_tokens = max_tokens if max_tokens != 9000 else 10000 # Adjust default if it was Groq's large default

        print(f"\n--- Using Claude LLM ({actual_model_name}) ---")
        try:
            # Claude API expects messages list and a separate system prompt
            messages_for_claude = [{"role": "user", "content": user_content_for_llm}]

            response_data = await claude_client.generate_message(
                messages=messages_for_claude,
                system_prompt=system_prompt_content_template, # System prompt passed here
                model=actual_model_name,
                max_tokens=claude_max_tokens,
                temperature=temperature
                # top_p is not directly used in the same way by Claude's Message API in basic calls
            )

            if response_data.get('content') and isinstance(response_data['content'], list):
                for block in response_data['content']:
                    if block.get('type') == 'text':
                        raw_response_text = block['text']
                        break # Take the first text block
            if not raw_response_text:
                print(f"Claude response did not contain expected text content: {response_data}")
                return None

        except ClaudeAPIError as cae:
            print(f"Claude API Error: Status {cae.status_code}, Type: {cae.error_type}, Message: {cae.error_message}")
            return None
        except Exception as e:
            print(f"Error transforming text with Claude: {e}")
            return None
    else:
        print(f"Unsupported LLM provider: {llm_provider}")
        return None

    if raw_response_text:
        print(f"Raw response from {llm_provider} model:\n{raw_response_text}")
        # Attempt to parse the response as JSON
        cleaned_response_for_json = raw_response_text.strip()
        if cleaned_response_for_json.startswith("```json"):
            cleaned_response_for_json = cleaned_response_for_json[len("```json"):].strip()
        if cleaned_response_for_json.endswith("```"):
            cleaned_response_for_json = cleaned_response_for_json[:-len("```")].strip()

        try:
            json_output = json.loads(cleaned_response_for_json)
            return json_output
        except json.JSONDecodeError as je:
            print(f"Error decoding JSON from model response: {je}")
            print(f"Cleaned response attempted for parsing:\n{cleaned_response_for_json}")
            return None
    else:
        print(f"No raw response text received from {llm_provider} model.")
        return None

async def main_async_example(): # Renamed and made async
    # ... (existing __main__ example for transform_to_script can remain synchronous if needed)
    # script = transform_to_script(input_text)
    # ...

    # Example for the new Tech in Asia script generator
    print("\n\n--- Tech in Asia Script Examples ---")
    tech_article_content = """
    Humane, a startup founded by ex-Apple veterans, launched its much-hyped Ai Pin in April 2024.
    The $699 screenless device, which attaches to clothing, aimed to revolutionize personal computing
    by offering AI-powered voice commands and a laser-projected display.
    However, early reviews were overwhelmingly negative, citing poor battery life, clunky user experience,
    and limited functionality. By May 2024, reports emerged that Humane was already seeking a buyer
    for $750 million to $1 billion, a steep valuation for a product with such a troubled launch.
    The situation highlights the immense challenges in creating truly innovative hardware, even for
    teams with impressive pedigrees and significant funding. Many critics questioned if the Ai Pin
    solved a real problem or was a solution in search of one.
    """

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    # Test with Groq (default)
    print("\nTesting with Groq...")
    tech_in_asia_script_groq = await transform_to_tech_in_asia_script(
        tech_article_content,
        llm_provider="groq"
        # model_name="mixtral-8x7b-32768" # Optionally specify a Groq model
    )
    if tech_in_asia_script_groq:
        output_json_path_groq = os.path.join(scripts_dir, "tech_in_asia_script_groq.json")
        with open(output_json_path_groq, "w") as f:
            json.dump(tech_in_asia_script_groq, f, indent=2)
        print(f"Tech in Asia script (Groq) JSON saved to {output_json_path_groq}")
    else:
        print("Failed to generate Tech in Asia script JSON with Groq.")

    # Test with Claude
    print("\nTesting with Claude...")
    tech_in_asia_script_claude = await transform_to_tech_in_asia_script(
        tech_article_content,
        llm_provider="claude",
        model_name="claude-3-haiku-20240307" # Using a smaller, faster Claude model for testing
        # temperature=0.5 # Optionally override temperature
    )
    if tech_in_asia_script_claude:
        output_json_path_claude = os.path.join(scripts_dir, "tech_in_asia_script_claude.json")
        with open(output_json_path_claude, "w") as f:
            json.dump(tech_in_asia_script_claude, f, indent=2)
        print(f"Tech in Asia script (Claude) JSON saved to {output_json_path_claude}")
    else:
        print("Failed to generate Tech in Asia script JSON with Claude.")

# Example usage
if __name__ == "__main__":
    # Original synchronous example (can be kept if desired)
    input_text_orig = """Tesla shares rose by 14.8% on Wednesday as investors speculated about possible policy changes under a Trump presidency.

The electric car maker, led by CEO Elon Musk, may benefit if subsidies for alternative energy decrease and tariffs on Chinese imports increase.

Other electric vehicle makers saw their stocks decline. Shanghai-based Nio's shares fell by 5.3%, while Rivian and Lucid Group's shares dropped by 8.3% and 5.3%, respectively.

Despite the surge, Tesla recently faced a downturn following an underwhelming robotaxi unveiling."""

    script = transform_to_script(input_text_orig)
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    if script:
        filename = os.path.join(scripts_dir, "transformed_script.txt")
        with open(filename, "w") as file:
            file.write(script)
        print(f"\n\nOriginal script saved to {filename}")

    # Run the new async example
    asyncio.run(main_async_example())
