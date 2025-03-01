import replicate

from dotenv import load_dotenv

load_dotenv()

def text_to_video(prompt, output_filename="videos/output.mp4"):
    """
    Convert text prompt to video using Replicate's Wan-2.1-1.3B model.
    
    Args:
        prompt (str): Text description of the video to generate
        output_filename (str): Filename to save the video (default: output.mp4)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        input = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
        }
        
        output = replicate.run(
            "wan-video/wan-2.1-1.3b",
            input=input
        )
        
        with open(output_filename, "wb") as file:
            file.write(output.read())
        
        print(f"Video saved to {output_filename}")
        return True
    
    except Exception as e:
        print(f"Error generating video: {e}")
        return False

# Example usage
if __name__ == "__main__":
    text_to_video("a dog is riding on a skateboard down a hill")
    #=> output.mp4 written to disk