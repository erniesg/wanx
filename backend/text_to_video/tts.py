import http.client
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)    

def text_to_speech(text, output_filename="output.mp3"):
    """
    Convert text to speech using Jigsawstack API and save to a file.
    
    Args:
        text (str): The text to convert to speech
        output_filename (str): Filename to save the audio (default: output.mp3)
    
    Returns:
        bool: True if successful, False otherwise
    """
    output_filename = f"audio/speech/{output_filename}"
    
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
        with open(output_filename, "wb") as audio_file:
            audio_file.write(data)
        return output_filename
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

# Example usage
if __name__ == "__main__":
    success = text_to_speech("Hello, how are you doing?")
    if success:
        logger.info(f"Audio saved successfully")
