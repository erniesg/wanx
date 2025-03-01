import http.client
import json
import os
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)    

def sanitize_filename(filename):
    """
    Sanitize a filename by removing spaces and special characters.
    
    Args:
        filename (str): The filename to sanitize
        
    Returns:
        str: Sanitized filename
    """
    # Replace spaces with underscores and remove special characters
    sanitized = re.sub(r'[^\w\-_.]', '_', filename.replace(' ', '_'))
    return sanitized

def text_to_speech(text, output_filename="output.mp3"):
    """
    Convert text to speech using Jigsawstack API and save to a file.
    
    Args:
        text (str): The text to convert to speech
        output_filename (str): Filename to save the audio (default: output.mp3)
    
    Returns:
        str: Path to the audio file if successful, False otherwise
    """
    # Sanitize the output filename
    output_filename = sanitize_filename(output_filename)
    
    # Create the audio directory if it doesn't exist
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    audio_dir = os.path.join(backend_dir,"assets", "audio", "speech")
    os.makedirs(audio_dir, exist_ok=True)
    
    # Set the full output path
    output_path = os.path.join(audio_dir, output_filename)
    
    conn = http.client.HTTPSConnection("api.jigsawstack.com")
    payload = json.dumps({
        "text": text
    })
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': os.getenv("JIGSAW_API_KEY")
    }
    
    try:
        conn.request("POST", "/v1/ai/tts", payload, headers)
        res = conn.getresponse()
        data = res.read()
        
        # Save the audio data to a file
        with open(output_path, "wb") as audio_file:
            audio_file.write(data)
        
        # Verify the file was created and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Audio file created successfully at {output_path}")
            return output_path
        else:
            logger.error(f"Failed to create audio file or file is empty: {output_path}")
            return False
            
    except Exception as e:
        logger.error(f"Error in text_to_speech: {e}")
        return False

# Example usage
if __name__ == "__main__":
    success = text_to_speech("Hello, how are you doing?")
    if success:
        logger.info(f"Audio saved successfully to {success}")
    else:
        logger.error("Failed to create audio file")
