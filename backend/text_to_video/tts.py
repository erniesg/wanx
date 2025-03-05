import os
import logging
import re
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import play

# Load environment variables
load_dotenv()

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
    Convert text to speech using ElevenLabs API and save to a file.

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
    audio_dir = os.path.join(backend_dir, "assets", "audio", "speech")
    os.makedirs(audio_dir, exist_ok=True)

    # Set the full output path
    output_path = os.path.join(audio_dir, output_filename)

    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    try:
        # Convert text to speech
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id="7W09sQ2BnuGV65vC8SCZ",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        # Collect audio data from the generator
        audio_data = b''.join(audio_generator)

        # Play the audio
        play(audio_data)

        # Save the audio data to a file
        with open(output_path, "wb") as audio_file:
            audio_file.write(audio_data)

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
    success = text_to_speech("Umm Al Qura's IPO sees massive demand—$126 billion in orders, 241 times oversubscribed! Shares priced at 15 riyals, valuing the company at $5.75 billion. The project aims")
    if success:
        logger.info(f"Audio saved successfully to {success}")
    else:
        logger.error("Failed to create audio file")
