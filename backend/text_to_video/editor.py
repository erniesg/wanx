from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import os

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

def combine_project(project_name, output_dir=None):
    """
    Find and combine audio and videos for a specific project.
    
    Args:
        project_name (str): Name of the project
        output_dir (str, optional): Directory to save the output file
        
    Returns:
        str: Path to the final video file
    """
    try:
        # Find the audio file
        audio_file = f"audio/speech/{project_name}.mp3"
        if not os.path.exists(audio_file):
            print(f"Audio file not found: {audio_file}")
            return None
            
        # Get all video files in the project directory
        video_dir = f"videos/{project_name}"
        if not os.path.exists(video_dir):
            print(f"Video directory not found: {video_dir}")
            return None
            
        # Get all mp4 files in the directory
        video_files = [os.path.join(video_dir, f) for f in os.listdir(video_dir) 
                      if f.endswith('.mp4') and not f.endswith('_final.mp4')]
        
        if not video_files:
            print(f"No video files found in directory: {video_dir}")
            return None
            
        print(f"Found audio: {audio_file}")
        print(f"Found {len(video_files)} videos: {video_files}")
        
        # Set output file path
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = f"{output_dir}/{project_name}_final.mp4"
        else:
            output_file = f"{video_dir}/{project_name}_final.mp4"
            
        # Combine audio and videos
        result = combine_audio_video(audio_file, video_files, output_file)
        return output_file
        
    except Exception as e:
        print(f"Error combining project: {e}")
        return None

# Test with "Tesla shar" project
if __name__ == "__main__":
    project_name = "Tesla shar"  # Using the original name with space
    result = combine_project(project_name)
    
    if result:
        print(f"Successfully created video: {result}")
    else:
        print("Failed to create video")
