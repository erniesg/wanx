import replicate
import os
from dotenv import load_dotenv

load_dotenv()

def text_to_video(prompt, output_filename=None):
    """
    Convert text prompt to video using Replicate's Wan-2.1-1.3B model.
    
    Args:
        prompt (str): Text description of the video to generate
        output_filename (str): Filename to save the video (default: auto-generated)
        
    Returns:
        str: Path to the saved video if successful, False otherwise
    """
    try:
        # If no output filename is provided, create one based on the prompt
        if output_filename is None:
            # Create videos directory in backend/assets
            videos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),  "videos")
            os.makedirs(videos_dir, exist_ok=True)
            
            # Create a filename from the first few words of the prompt
            safe_prompt = "".join(c if c.isalnum() else "_" for c in prompt[:20])
            output_filename = os.path.join(videos_dir, f"{safe_prompt}.mp4")
        
        input = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
        }
        
        output = replicate.run(
            "wan-video/wan-2.1-1.3b",
            input=input
        )
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        
        with open(output_filename, "wb") as file:
            file.write(output.read())
        
        print(f"Video saved to {output_filename}")
        return output_filename
    
    except Exception as e:
        print(f"Error generating video: {e}")
        return False

# Example usage
if __name__ == "__main__":
    result = text_to_video("a dog is riding on a skateboard down a hill")
    if result:
        print(f"Video successfully saved to: {result}")
    else:
        print("Failed to generate video")