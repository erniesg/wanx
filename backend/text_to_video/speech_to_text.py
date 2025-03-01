import os
from groq import Groq

def transcribe_audio(audio_file_path,  response_format="verbose_json"):
    """
    Transcribe audio file to text using Groq's Whisper model.
    
    Args:
        audio_file_path (str): Path to the audio file
        prompt (str, optional): Optional prompt to guide transcription
        response_format (str): Format of the response (default: verbose_json)
        
    Returns:
        str: Transcribed text
    """
    client = Groq()
    
    try:
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(audio_file_path, file.read()),
                model="whisper-large-v3-turbo",
                response_format=response_format,
            )
        return transcription
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None

# Example usage
if __name__ == "__main__":
    filename = os.path.dirname(__file__) + "/audio/speech/output.mp3"
    result = transcribe_audio(filename)
    print(result)