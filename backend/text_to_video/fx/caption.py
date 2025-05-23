import subprocess
import tempfile
import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
from moviepy.video.fx.all import crop, resize
from backend.text_to_video.fx import add_captions

TIKTOK_DIMS = (1080, 1920)

def ffmpeg_cmd(command):
    # Simplified ffmpeg command execution
    try:
        print(f"Running FFmpeg command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print("FFmpeg stdout:", result.stdout)
        print("FFmpeg stderr:", result.stderr)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing FFmpeg command: {' '.join(command)}")
        print("FFmpeg stdout:", e.stdout)
        print("FFmpeg stderr:", e.stderr)
        raise

def create_captioned_video(
    video_path: str,
    audio_path: str,
    output_directory: str,
    output_filename: str = "captioned_video.mp4",
    font: str = "Bangers-Regular.ttf",
    font_size: int = 80, # Adjusted for vertical format
    font_color: str = "yellow",
    stroke_width: int = 2, # Adjusted for vertical format
    stroke_color: str = "black",
    highlight_current_word: bool = True,
    word_highlight_color: str = "red",
    line_count: int = 1, # Adjusted for more vertical space
    padding: int = 50, # Adjusted for vertical format
    position: tuple = "bottom-center",
    shadow_strength: float = 0.5, # Adjusted for subtlety
    shadow_blur: float = 0.05, # Adjusted for subtlety
    print_info: bool = False,
    initial_prompt: str = None,
    segments: list = None,
    use_local_whisper: str = "auto",
):
    """
    Creates a captioned video by combining a video and audio file,
    resizing/cropping for TikTok dimensions, and adding captions.
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    output_path = os.path.join(output_directory, output_filename)
    processed_video_path = os.path.join(tempfile.gettempdir(), f"processed_{os.path.basename(video_path)}")

    # 1. Combine audio with video and shorten/extend video if necessary
    # Load video and audio
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)
    original_audio_duration = audio_clip.duration

    # Determine FPS from the video clip. Use a default if FPS is None or 0.
    fps = video_clip.fps if video_clip.fps and video_clip.fps > 0 else 30.0
    if print_info and (video_clip.fps is None or video_clip.fps <= 0):
        print(f"Warning: Video FPS was {video_clip.fps}, using default {fps} fps.")

    # Calculate target total frames based on original audio duration and video FPS
    target_total_frames = round(original_audio_duration * fps)
    precise_target_duration = target_total_frames / fps

    if print_info:
        print(f"Original video duration: {video_clip.duration}s, Original audio duration: {original_audio_duration}s")
        print(f"Video FPS: {fps}")
        print(f"Target total frames (based on audio): {target_total_frames}")
        print(f"Precise target duration (for video and audio): {precise_target_duration}s")

    # If video has its own audio, remove it
    video_clip = video_clip.without_audio()

    # Set video and audio durations precisely based on frame count
    video_clip = video_clip.set_duration(precise_target_duration)
    audio_clip = audio_clip.set_duration(precise_target_duration)

    # Combine new audio
    final_clip_with_audio = video_clip.set_audio(audio_clip)
    final_clip_with_audio = final_clip_with_audio.set_duration(precise_target_duration)

    # Write this intermediate clip to a temporary file
    temp_video_audio_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    if print_info:
        print(f"Writing intermediate video with new audio to: {temp_video_audio_path}")
        print(f"  Expected duration for temp_video_audio_path: {precise_target_duration}s, Expected frames: {target_total_frames}, FPS: {final_clip_with_audio.fps}") # FPS might be slightly different after processing
    final_clip_with_audio.write_videofile(temp_video_audio_path, codec="libx264", audio_codec="aac", logger="bar" if print_info else None, fps=fps) # Enforce FPS on write

    # 2. Scale down for TikTok dimensions, then center crop
    # Load the combined clip
    clip_to_resize = VideoFileClip(temp_video_audio_path)
    clip_to_resize = clip_to_resize.set_duration(precise_target_duration)

    # Calculate new width and height maintaining aspect ratio to fit within TikTok dimensions
    original_width, original_height = clip_to_resize.size
    tiktok_width, tiktok_height = TIKTOK_DIMS

    # Resize to fit the height of TikTok, width will adjust proportionally
    scale_factor_h = tiktok_height / original_height
    new_width_h = original_width * scale_factor_h

    # Resize to fit the width of TikTok, height will adjust proportionally
    scale_factor_w = tiktok_width / original_width
    new_height_w = original_height * scale_factor_w

    if new_width_h >= tiktok_width: # If scaled by height, width is still too large or just right
        resized_clip = clip_to_resize.resize(height=tiktok_height)
    else: # Scaled by height makes width too small, so scale by width instead
        resized_clip = clip_to_resize.resize(width=tiktok_width)

    # Center crop if there's overspill
    # The crop fx takes (x_center, y_center, width, height)
    # We want to crop from the center of the resized clip
    x_center = resized_clip.w / 2
    y_center = resized_clip.h / 2

    cropped_clip = crop(resized_clip, x_center=x_center, y_center=y_center, width=tiktok_width, height=tiktok_height)
    cropped_clip = cropped_clip.set_duration(precise_target_duration)

    if print_info:
        print(f"Resized to: ({resized_clip.w}, {resized_clip.h}), Cropped to: ({cropped_clip.w}, {cropped_clip.h})")
        print(f"  Duration of cropped_clip before writing to processed_video_path: {cropped_clip.duration}s, Expected frames: {target_total_frames}, FPS: {cropped_clip.fps}")

    cropped_clip.write_videofile(processed_video_path, codec="libx264", audio_codec="aac", logger="bar" if print_info else None, fps=fps) # Enforce FPS on write

    # Close clips to free up resources
    video_clip.close()
    audio_clip.close()
    final_clip_with_audio.close()
    clip_to_resize.close()
    resized_clip.close()
    cropped_clip.close()

    # 3. Add captions using the existing add_captions function
    if print_info:
        print(f"Adding captions to: {processed_video_path}")

    add_captions(
        video_file=processed_video_path,
        output_file=output_path,
        font=font,
        font_size=font_size,
        font_color=font_color,
        stroke_width=stroke_width,
        stroke_color=stroke_color,
        highlight_current_word=highlight_current_word,
        word_highlight_color=word_highlight_color,
        line_count=line_count,
        padding=padding,
        position=position,
        shadow_strength=shadow_strength,
        shadow_blur=shadow_blur,
        print_info=print_info,
        initial_prompt=initial_prompt,
        segments=segments,
        use_local_whisper=use_local_whisper,
    )

    # Clean up temporary file used for audio merge
    if os.path.exists(temp_video_audio_path):
        os.remove(temp_video_audio_path)
    if os.path.exists(processed_video_path): # This one might be cleaned by add_captions if it uses NamedTemporaryFile without delete=False
       try:
           os.remove(processed_video_path)
       except Exception as e:
           if print_info:
               print(f"Could not remove temporary processed video: {processed_video_path}, error: {e}")


    if print_info:
        print(f"Final captioned video saved to: {output_path}")

    return output_path

if __name__ == '__main__':
    # Example usage:
    # Ensure this script is in the backend/text_to_video/fx directory
    # and your assets are correctly pathed relative to the workspace root.

    # Correcting paths for direct execution from workspace root if needed
    # This assumes __main__ is run when the script is in its intended location
    # or paths are adjusted if run from elsewhere.

    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

    test_video = os.path.join(workspace_root, "backend/assets/test/clip.mov")
    test_audio = os.path.join(workspace_root, "backend/assets/test/test.mp3")
    output_dir = os.path.join(workspace_root, "backend/assets/output")

    if not os.path.exists(test_video):
        print(f"Test video not found: {test_video}")
    if not os.path.exists(test_audio):
        print(f"Test audio not found: {test_audio}")

    if os.path.exists(test_video) and os.path.exists(test_audio):
        print("Running example...")
        create_captioned_video(
            video_path=test_video,
            audio_path=test_audio,
            output_directory=output_dir,
            output_filename="tiktok_test_output.mp4",
            print_info=True,
            font_size=80, # Smaller font for testing
            line_count=1, # Changed from 3 to 1
            padding=50,
            position="bottom-center"
        )
        print(f"Example finished. Check {output_dir}")
    else:
        print("Cannot run example, missing test files.")
