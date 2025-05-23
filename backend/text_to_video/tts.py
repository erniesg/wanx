import os
import logging
import re
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import play, Voice, VoiceSettings

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default values from your config, to be used if not overridden by function call
DEFAULT_VOICE_ID = "SDNKIYEpTz0h56jQX8rA"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_SPEED = 1.15
DEFAULT_STABILITY = 0.50
DEFAULT_SIMILARITY_BOOST = 0.75
DEFAULT_STYLE = 0.0  # Style Exaggeration 0%
DEFAULT_USE_SPEAKER_BOOST = True

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

def text_to_speech(
    text: str,
    output_filename: str = "output.mp3",
    voice_id: str = DEFAULT_VOICE_ID,
    model_id: str = DEFAULT_MODEL_ID,
    speed: float = DEFAULT_SPEED,
    stability: float = DEFAULT_STABILITY,
    similarity_boost: float = DEFAULT_SIMILARITY_BOOST,
    style: float = DEFAULT_STYLE,
    use_speaker_boost: bool = DEFAULT_USE_SPEAKER_BOOST,
    output_format: str = "mp3_44100_128"
):
    """
    Convert text to speech using ElevenLabs API and save to a file.

    Args:
        text (str): The text to convert to speech
        output_filename (str): Filename to save the audio (default: output.mp3)
        voice_id (str): ID of the voice to use.
        model_id (str): ID of the model to use.
        speed (float): Speed of the speech.
        stability (float): Stability of the speech.
        similarity_boost (float): Similarity boost for the speech.
        style (float): Style exaggeration for the speech.
        use_speaker_boost (bool): Whether to use speaker boost.
        output_format (str): The format of the output audio file.

    Returns:
        str: Path to the audio file if successful, False otherwise
    """

    # Sanitize the output filename
    output_filename = sanitize_filename(output_filename)

    # Create the audio directory if it doesn't exist
    # backend/assets/audio/speech
    # __file__ is .../backend/text_to_video/tts.py
    # os.path.dirname(__file__) is .../backend/text_to_video
    # os.path.dirname(os.path.dirname(__file__)) is .../backend
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    audio_dir = os.path.join(backend_dir, "assets", "audio", "speech")
    os.makedirs(audio_dir, exist_ok=True)

    # Set the full output path
    output_path = os.path.join(audio_dir, output_filename)

    # Initialize ElevenLabs client
    # The API key is passed during initialization and handled internally by the client.
    # An explicit check like `if not client.api_key:` is not needed and can cause
    # an AttributeError with recent versions of the elevenlabs-python SDK.
    # If the API key is missing or invalid, API calls will fail and should be caught by the try-except block.
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    try:
        # Define voice settings using provided parameters
        # Note: The `speed` parameter for VoiceSettings might depend on the SDK version or may not be standard.
        # If issues arise, check the specific elevenlabs SDK documentation for VoiceSettings capabilities.
        voice_settings_params = {
            "stability": stability,
            "similarity_boost": similarity_boost,
        }
        # Some parameters like style and use_speaker_boost might only be available on newer models/SDK versions
        # or might have different names. The current SDK (v1.x) uses these names for VoiceSettings.
        if style is not None: # style can be 0.0 so check for None
            voice_settings_params["style"] = style
        if use_speaker_boost is not None:
            voice_settings_params["use_speaker_boost"] = use_speaker_boost

        # The `speed` parameter is not a standard constructor argument for `elevenlabs.VoiceSettings` in v1.x.
        # If your SDK version or specific setup supports `speed` directly in `VoiceSettings`,
        # you would include it here. The original tts.py had `speed=1.15` in the constructor call.
        # I am including it as it was in the original user code, assuming their SDK version might allow it.
        # If it causes an error, it should be removed or handled according to the SDK version.
        if speed is not None: # Check if speed is intended to be set
             voice_settings_params['speed'] = speed

        custom_voice_settings = VoiceSettings(**voice_settings_params)

        logger.info(f"Requesting TTS with settings: voice_id={voice_id}, model_id={model_id}, speed={speed}, stability={stability}, similarity_boost={similarity_boost}, style={style}, use_speaker_boost={use_speaker_boost}")

        # Convert text to speech
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format,
            voice_settings=custom_voice_settings
        )

        # Collect audio data from the generator
        audio_data = b''.join(audio_generator)

        # Play the audio (optional, can be removed if not needed for CLI usage)
        # play(audio_data)

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
        # If it's an API error from ElevenLabs, it might be an anthropic.APIError or similar
        # For example, if `speed` is an invalid parameter for VoiceSettings in the used SDK version.
        if "got an unexpected keyword argument 'speed'" in str(e):
            logger.error("The 'speed' parameter might not be supported by VoiceSettings in your ElevenLabs SDK version.")
        return False

# Example usage
if __name__ == "__main__":
    logger.info("Testing TTS with default parameters...")
    success_default = text_to_speech(
        "Umm Al Qura's IPO sees massive demand—$126 billion in orders, 241 times oversubscribed!",
        output_filename="ipo_test_default_settings.mp3"
    )
    if success_default:
        logger.info(f"Default TTS audio saved successfully to {success_default}")
    else:
        logger.error("Failed to create default TTS audio file")

    logger.info("\nTesting TTS with some custom parameters (example values)...")
    success_custom = text_to_speech(
        "This is a test with custom voice settings for speed and style.",
        output_filename="custom_settings_test.mp3",
        voice_id=DEFAULT_VOICE_ID, # Can use a different one if available
        model_id=DEFAULT_MODEL_ID, # Or a different model
        speed=1.0, # Slower speed
        stability=0.60,
        similarity_boost=0.70,
        style=0.05, # A little bit of style
        use_speaker_boost=False
    )
    if success_custom:
        logger.info(f"Custom TTS audio saved successfully to {success_custom}")
    else:
        logger.error("Failed to create custom TTS audio file")
