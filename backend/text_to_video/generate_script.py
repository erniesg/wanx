from groq import Groq
import os

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
                    "content": f"Transform this text #Content {input_text} and transform that into a short form content for tiktok and youtube shorts we just want the content that the human should read. only give the text that i should be reading. no hashtags at the end"
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
