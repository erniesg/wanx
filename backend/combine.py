import os
from typing import List, Dict, Optional, Tuple
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from moviepy import vfx, afx  # Import video and audio effects

def combine_videos(
    folder_path: str,
    subtitle_text: str = None,
    vo_volume: float = 1.0,
    bg_volume: float = 0.3,
    output_path: str = None,  # Changed to None default
    font: str = "Arial",
    font_size: int = 30,
    font_color: str = "white",
    transition_duration: float = 0.5
) -> str:
    """
    Combine video scenes with voiceover, background music, and a single subtitle.

    Args:
        folder_path: Path to folder containing assets
        subtitle_text: Text to display as subtitle throughout the video
        vo_volume: Volume for voiceover (0.0 to 1.0)
        bg_volume: Volume for background music (0.0 to 1.0)
        output_path: Path for the output video (if None, saves to assets folder)
        font: Font for subtitles
        font_size: Font size for subtitles
        font_color: Font color for subtitles
        transition_duration: Duration of transitions between scenes in seconds

    Returns:
        Path to the output video file
    """
    # Check if folder exists
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder {folder_path} not found")

    # If output_path is None, save to the assets folder
    if output_path is None:
        output_path = os.path.join(folder_path, "output.mp4")

    # Load video scenes
    scene_clips = []
    scene_index = 1

    while True:
        scene_path = os.path.join(folder_path, f"scene{scene_index}.mp4")
        if not os.path.exists(scene_path):
            break

        clip = VideoFileClip(scene_path)
        scene_clips.append(clip)
        scene_index += 1

    if not scene_clips:
        raise FileNotFoundError(f"No scene files found in {folder_path}")

    # Apply transitions between clips
    clips_with_transitions = []

    for i, clip in enumerate(scene_clips):
        if i < len(scene_clips) - 1:
            # Apply crossfade out to current clip
            current_clip = clip.with_effects([vfx.CrossFadeOut(transition_duration)])
            clips_with_transitions.append(current_clip)

            # Apply crossfade in to next clip
            next_clip = scene_clips[i+1].with_effects([vfx.CrossFadeIn(transition_duration)])

            # The next clip will be added in the next iteration or at the end
            if i == len(scene_clips) - 2:  # If this is the second-to-last clip
                clips_with_transitions.append(next_clip)
        elif i == 0:  # If there's only one clip
            clips_with_transitions.append(clip)

    # Concatenate video scenes with transitions
    final_video = concatenate_videoclips(clips_with_transitions, method="compose")

    # Load voiceover
    vo_path = os.path.join(folder_path, "vo.mp3")
    if not os.path.exists(vo_path):
        raise FileNotFoundError(f"Voiceover file {vo_path} not found")

    vo_audio = AudioFileClip(vo_path).with_volume_scaled(vo_volume)
    # Add a gentle fadeout to the voiceover
    vo_audio = vo_audio.with_effects([afx.AudioFadeOut(1.0)])

    # Load background music if it exists
    bg_path = os.path.join(folder_path, "bg.mp3")
    if os.path.exists(bg_path):
        bg_audio = AudioFileClip(bg_path).with_volume_scaled(bg_volume)

        # If background is shorter than video, loop it
        if bg_audio.duration < final_video.duration:
            bg_audio = bg_audio.with_effects([afx.AudioLoop(duration=final_video.duration)])
        else:
            # Trim background if longer than video
            bg_audio = bg_audio.subclip(0, final_video.duration)

        # Add a fadeout to the background music
        bg_audio = bg_audio.with_effects([afx.AudioFadeOut(2.0)])

        # Mix voiceover and background
        from moviepy.audio.AudioClip import CompositeAudioClip
        final_audio = CompositeAudioClip([bg_audio, vo_audio])
    else:
        final_audio = vo_audio

    # Set audio to video
    final_video = final_video.with_audio(final_audio)

    # Add subtitle if provided
    if subtitle_text:
        # Create a text clip with word wrapping for better readability
        # Limit width to 80% of video width
        video_width = final_video.w
        txt_clip = TextClip(
            text=subtitle_text,
            font_size=font_size,
            font=font,
            color=font_color,
            bg_color=None,  # Transparent background
            method='caption',
            text_align='center',
            size=(int(video_width * 0.8), None),  # Width constraint for word wrapping
            stroke_color='black',
            stroke_width=1
        )

        # Position at center of the video frame
        txt_clip = txt_clip.with_position('center').with_duration(final_video.duration)

        # Add subtitle to video
        final_video = CompositeVideoClip([final_video, txt_clip])

    # Write final video
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")

    # Close all clips to free resources
    for clip in scene_clips:
        clip.close()
    vo_audio.close()
    if 'bg_audio' in locals():
        bg_audio.close()
    final_video.close()

    return output_path

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Combine video scenes with audio and subtitles")
    parser.add_argument("--folder", default="assets/demo", help="Folder containing assets")
    parser.add_argument("--output", default=None, help="Output video path (default: save to assets folder)")
    parser.add_argument("--vo-volume", type=float, default=1.0, help="Voiceover volume (0.0-1.0)")
    parser.add_argument("--bg-volume", type=float, default=0.3, help="Background music volume (0.0-1.0)")
    parser.add_argument("--subtitle", default=None, help="Subtitle text to display")
    parser.add_argument("--transition", type=float, default=0.5, help="Transition duration in seconds")

    args = parser.parse_args()

    # Default subtitle text if none provided
    default_subtitle = "Breaking tech news: 22 locations raided, 9 arrested - but who's really behind the illegal movement of restricted Nvidia AI chips from Singapore to China? Get the full shocking details - link in bio."

    subtitle_text = args.subtitle if args.subtitle else default_subtitle

    try:
        output_file = combine_videos(
            folder_path=args.folder,
            subtitle_text=subtitle_text,
            vo_volume=args.vo_volume,
            bg_volume=args.bg_volume,
            output_path=args.output,
            transition_duration=args.transition
        )
        print(f"Video successfully created: {output_file}")
    except Exception as e:
        print(f"Error: {e}")
