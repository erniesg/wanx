from groq import Groq
import os
import json

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

def transform_to_tech_in_asia_script(input_text, temperature=0.6, max_tokens=9000, top_p=0.95):
    """
    Transform any text into a Tech in Asia style video script using Groq's AI model,
    expecting a JSON output.

    Args:
        input_text (str): The text to transform into a script.
        temperature (float): Controls randomness (0.0-1.0).
        max_tokens (int): Maximum number of tokens to generate.
        top_p (float): Controls diversity via nucleus sampling.

    Returns:
        dict: The generated script as a Python dictionary, or None if an error occurs.
    """
    client = Groq()

    # Determine the path to the prompt file relative to this script's location
    # Assuming this script is in backend/text_to_video/ and prompt is in config/
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file_path = os.path.join(current_dir, "..", "..", "config", "tech_in_asia_script_prompt.md")

    try:
        with open(prompt_file_path, "r") as f:
            system_prompt_content = f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {prompt_file_path}")
        return None
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        return None

    # The prompt already asks for JSON output, so we just pass the content.
    # We add a specific instruction to ensure JSON output.
    user_content = f"{input_text}\\n\\nEnsure the output is a valid JSON object adhering to the specified <output_format>."


    try:
        completion = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b", # Or another suitable model
            messages=[
                {
                    "role": "system",
                    "content": system_prompt_content
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            temperature=temperature,
            top_p=top_p,
            stream=False, # Set to False to get the full response for JSON parsing
            # Consider adding response_format if the Groq API/model supports it explicitly for JSON
            # response_format={"type": "json_object"}, # Example if supported
            stop=None,
        )

        raw_response = completion.choices[0].message.content
        print(f"Raw response from model:\\n{raw_response}")

        # Attempt to parse the response as JSON
        # The LLM might sometimes include markdown ```json ... ``` around the JSON
        cleaned_response_for_json = raw_response.strip()
        if cleaned_response_for_json.startswith("```json"):
            cleaned_response_for_json = cleaned_response_for_json[len("```json"):].strip()
        if cleaned_response_for_json.endswith("```"):
            cleaned_response_for_json = cleaned_response_for_json[:-len("```")].strip()

        try:
            json_output = json.loads(cleaned_response_for_json)
            return json_output
        except json.JSONDecodeError as je:
            print(f"Error decoding JSON from model response: {je}")
            print(f"Cleaned response attempted for parsing:\\n{cleaned_response_for_json}")
            return None # Or could return the raw string for manual inspection

    except Exception as e:
        print(f"Error transforming text for Tech in Asia script: {e}")
        return None

# Example usage
if __name__ == "__main__":
    input_text = """Tesla shares rose by 14.8% on Wednesday as investors speculated about possible policy changes under a Trump presidency.

The electric car maker, led by CEO Elon Musk, may benefit if subsidies for alternative energy decrease and tariffs on Chinese imports increase.

Other electric vehicle makers saw their stocks decline. Shanghai-based Nio's shares fell by 5.3%, while Rivian and Lucid Group's shares dropped by 8.3% and 5.3%, respectively.

Despite the surge, Tesla recently faced a downturn following an underwhelming robotaxi unveiling."""

    # Transform the text
    script = transform_to_script(input_text)

    # Optionally save to file
    if script:
        # Create scripts directory in backend/assets
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "scripts")
        os.makedirs(scripts_dir, exist_ok=True)

        filename = os.path.join(scripts_dir, "transformed_script.txt")
        with open(filename, "w") as file:
            file.write(script)
        print(f"\n\nScript saved to {filename}")

    # Example for the new Tech in Asia script generator
    print("\n\n--- Tech in Asia Script Example ---")
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
    tech_in_asia_script_json = transform_to_tech_in_asia_script(tech_article_content)

    if tech_in_asia_script_json:
        output_json_path = os.path.join(scripts_dir, "tech_in_asia_script.json")
        with open(output_json_path, "w") as f:
            json.dump(tech_in_asia_script_json, f, indent=2)
        print(f"Tech in Asia script JSON saved to {output_json_path}")
        # print(json.dumps(tech_in_asia_script_json, indent=2))
    else:
        print("Failed to generate Tech in Asia script JSON.")
