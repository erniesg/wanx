import pathlib
from moviepy.editor import ImageClip, VideoFileClip, CompositeVideoClip
from moviepy.video.fx.all import resize, crop

# Standard TikTok dimensions (width, height)
TIKTOK_DIMS = (1080, 1920)
DEFAULT_FPS = 24 # Default FPS for image-derived clips

def process_image_to_video_clip(
    image_path: str,
    duration: float,
    target_dims: tuple[int, int] = TIKTOK_DIMS,
    fps: int = DEFAULT_FPS
) -> CompositeVideoClip | None:
    """
    Loads an image, converts it to a video clip of a specific duration,
    resizes it to fill target dimensions, and then center-crops.

    Args:
        image_path: Path to the image file.
        duration: Desired duration of the video clip.
        target_dims: Tuple (width, height) for the output clip.
        fps: Frames per second for the resulting video clip.

    Returns:
        A MoviePy CompositeVideoClip, or None if an error occurs.
    """
    try:
        if not pathlib.Path(image_path).exists():
            print(f"Error: Image file not found at {image_path}")
            return None

        img_clip = ImageClip(image_path)

        # Resize to fill target_dims then center crop
        original_w, original_h = img_clip.size
        target_w, target_h = target_dims

        if original_w == 0 or original_h == 0:
            print(f"Error: Image at {image_path} has zero dimensions.")
            return None

        ar_original = original_w / original_h
        ar_target = target_w / target_h

        if ar_original > ar_target: # Original is wider than target (needs crop on sides)
            # Resize by height, width will be > target_w
            resized_clip_for_crop = img_clip.resize(height=target_h)
        else: # Original is taller or same aspect as target (needs crop on top/bottom)
            # Resize by width, height will be > target_h
            resized_clip_for_crop = img_clip.resize(width=target_w)

        # Center crop
        processed_clip = crop(resized_clip_for_crop,
                              width=target_w, height=target_h,
                              x_center=resized_clip_for_crop.w / 2,
                              y_center=resized_clip_for_crop.h / 2)

        # Set duration and FPS for the final clip from image
        # ImageClip needs to be explicitly set with duration and fps
        # To make it a VideoClip, we can put it on a ColorClip bg or use CompositeVideoClip
        # Forcing it onto a CompositeVideoClip ensures it behaves like a standard video clip.
        final_video_clip = processed_clip.set_duration(duration).set_fps(fps)

        # Ensure the output is a CompositeVideoClip for consistency, sized correctly
        # This handles cases where the processed_clip might not be a CompositeVideoClip directly
        # and ensures it has a definite size.
        return CompositeVideoClip([final_video_clip], size=target_dims).set_duration(duration)

    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

def process_video_clip(
    video_path: str,
    scene_duration: float,
    target_dims: tuple[int, int] = TIKTOK_DIMS
) -> VideoFileClip | None:
    """
    Loads a video clip, sets its duration for the scene,
    resizes it to fill target dimensions, and then center-crops.

    Args:
        video_path: Path to the video file.
        scene_duration: Desired duration of the clip for the scene.
        target_dims: Tuple (width, height) for the output clip.

    Returns:
        A MoviePy VideoFileClip, or None if an error occurs.
    """
    try:
        if not pathlib.Path(video_path).exists():
            print(f"Error: Video file not found at {video_path}")
            return None

        clip = VideoFileClip(video_path, audio=True) # Keep audio for now, might be stripped later

        # Set duration for the scene.
        # If scene_duration is longer than clip, MoviePy loops by default or can be made to freeze last frame.
        # For simplicity, we are taking a subclip. If video is shorter, it will be shorter.
        # The assembler should handle if a video is too short. Here we just trim/take subclip.
        if clip.duration < scene_duration:
            print(f"Warning: Video at {video_path} (duration {clip.duration:.2f}s) is shorter than required scene duration {scene_duration:.2f}s. It will be used as is for its full duration.")
            clip = clip.set_duration(clip.duration) # Use its own full duration
        else:
            clip = clip.subclip(0, scene_duration)

        # Ensure it has a duration after subclip
        clip = clip.set_duration(scene_duration if clip.duration >= scene_duration else clip.duration)


        # Resize to fill target_dims then center crop
        original_w, original_h = clip.size
        target_w, target_h = target_dims

        if original_w == 0 or original_h == 0:
            print(f"Error: Video at {video_path} has zero dimensions.")
            clip.close()
            return None

        ar_original = original_w / original_h
        ar_target = target_w / target_h

        if ar_original > ar_target: # Original is wider than target
            resized_clip_for_crop = resize(clip, height=target_h)
        else: # Original is taller or same aspect as target
            resized_clip_for_crop = resize(clip, width=target_w)

        processed_clip = crop(resized_clip_for_crop,
                               width=target_w, height=target_h,
                               x_center=resized_clip_for_crop.w / 2,
                               y_center=resized_clip_for_crop.h / 2)

        # Ensure duration is correctly set on the final processed clip
        return processed_clip.set_duration(scene_duration if processed_clip.duration >= scene_duration else processed_clip.duration)

    except Exception as e:
        print(f"Error processing video {video_path}: {e}")
        if 'clip' in locals() and hasattr(clip, 'close'):
            clip.close()
        return None
