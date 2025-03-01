from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import os
import logging

def combine_audio_video(audio_file, video_files, output_file="final_tiktok.mp4"):
    """
    Combine audio with multiple video clips to create a TikTok video.

    Args:
        audio_file (str): Path to the audio file
        video_files (list): List of paths to video files
        output_file (str): Path for the output video file

    Returns:
        str: Path to the final video file
    """
    try:
        # Load the audio file
        audio = AudioFileClip(audio_file)
        audio_duration = audio.duration

        # Load video clips
        video_clips = []
        for video_path in video_files:
            clip = VideoFileClip(video_path)
            video_clips.append(clip)

        # Concatenate video clips
        final_clip = concatenate_videoclips(video_clips)

        # If the combined video is shorter than the audio, loop the video
        if final_clip.duration < audio_duration:
            # Calculate how many times to loop
            loop_count = int(audio_duration / final_clip.duration) + 1
            looped_clips = []
            for _ in range(loop_count):
                looped_clips.extend(video_clips)

            final_clip = concatenate_videoclips(looped_clips)

        # Trim the video to match audio duration
        final_clip = final_clip.subclip(0, audio_duration)

        # Add the audio to the video
        final_clip = final_clip.set_audio(audio)

        # Write the result to a file
        final_clip.write_videofile(output_file, codec="libx264", audio_codec="aac")

        # Close the clips to free resources
        audio.close()
        final_clip.close()
        for clip in video_clips:
            clip.close()

        return output_file

    except Exception as e:
        print(f"Error combining audio and video: {e}")
        return None

def combine_project(project_name, audio_path=None):
    """
    Combine all assets for a project into a final video.

    Args:
        project_name (str): Name of the project
        audio_path (str, optional): Full path to the audio file

    Returns:
        str: Path to the final video
    """
    # Create necessary directories with consistent paths
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    assets_dir = os.path.join(backend_dir, "assets")
    audio_dir = os.path.join(assets_dir, "audio", "speech")
    videos_dir = os.path.join(assets_dir, "videos", project_name)
    output_dir = os.path.join(assets_dir, "output")

    os.makedirs(output_dir, exist_ok=True)

    # If audio_path is not provided, use the default location
    if not audio_path:
        audio_path = os.path.join(audio_dir, f"{project_name}.mp3")

    # Verify audio file exists
    if not os.path.exists(audio_path):
        logging.error(f"Audio file not found: {audio_path}")
        return None

    # Additional validation for audio file
    logging.info(f"Validating audio file: {audio_path}")
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(audio_path)
        logging.info(f"Audio file is valid, duration: {len(audio)/1000} seconds")
    except Exception as e:
        logging.error(f"Audio file validation failed: {str(e)}")
        # Try to create a silent audio file as fallback
        try:
            logging.info("Creating silent audio as fallback")
            from pydub import AudioSegment
            silent_audio = AudioSegment.silent(duration=30000)  # 30 seconds of silence
            silent_audio.export(audio_path, format="mp3")
            logging.info(f"Created silent audio file: {audio_path}")
        except Exception as e2:
            logging.error(f"Failed to create silent audio: {str(e2)}")
            return None

    # Get video files
    video_files = []
    for file in sorted(os.listdir(videos_dir)):
        if file.endswith(".mp4"):
            video_files.append(os.path.join(videos_dir, file))

    if not video_files:
        logging.error(f"No video files found in {videos_dir}")
        return None

    logging.info(f"Found {len(video_files)} video files to combine")
    for i, video in enumerate(video_files):
        logging.info(f"Video {i+1}: {os.path.basename(video)}")

    # Combine audio and videos
    output_file = os.path.join(output_dir, f"{project_name}_tiktok.mp4")
    return combine_audio_video(audio_path, video_files, output_file)

# Test with "Tesla shar" project
if __name__ == "__main__":
    project_name = "Tesla shar"  # Using the original name with space
    result = combine_project(project_name)

    if result:
        print(f"Successfully created video: {result}")
    else:
        print("Failed to create video")
