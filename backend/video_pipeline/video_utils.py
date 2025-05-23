import pathlib
import tempfile
import os
from moviepy.editor import ImageClip, VideoFileClip, CompositeVideoClip
from moviepy.video.fx.all import resize, crop
import logging

# Standard TikTok dimensions (width, height)
# TIKTOK_DIMS = (1080, 1920) # Will be passed by caller
# DEFAULT_FPS = 24 # Default FPS for image-derived clips. Will be passed by caller

# Setup logger for this module
logger = logging.getLogger(__name__)
# Ensure the logger is configured to output messages if not already configured by calling script
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Directory for temporary processed clips from video_utils
# Ensure this directory exists or is created by the calling script
TEMP_PROCESSED_CLIPS_DIR = pathlib.Path(tempfile.gettempdir()) / "wanx_temp_processed_clips"
TEMP_PROCESSED_CLIPS_DIR.mkdir(parents=True, exist_ok=True)

def process_image_to_video_clip(
    image_path: str,
    duration: float,
    target_dims: tuple[int, int], # Ensure this is always provided
    fps: int # Ensure this is always provided
) -> CompositeVideoClip | None:
    """
    Loads an image, converts it to a video clip of a specific duration,
    resizes it to "cover" target dimensions (maintaining aspect ratio, potentially overfilling),
    and then center-crops to the exact target dimensions.
    """
    try:
        if not pathlib.Path(image_path).exists():
            logger.error(f"Image file not found at {image_path}")
            return None

        img_clip_initial = ImageClip(image_path)
        original_w, original_h = img_clip_initial.size
        target_w, target_h = target_dims

        if original_w == 0 or original_h == 0:
            logger.error(f"Image at {image_path} has zero dimensions.")
            if hasattr(img_clip_initial, 'close'): img_clip_initial.close()
            return None

        # Calculate aspect ratios
        ar_original = original_w / original_h
        ar_target = target_w / target_h

        # Scale to cover/fill target dimensions while maintaining aspect ratio
        if ar_original > ar_target:
            # Original is wider than target aspect ratio. Scale by height.
            # New width will be original_w * (target_h / original_h)
            # This new width will be >= target_w.
            scaled_clip = img_clip_initial.resize(height=target_h)
        else:
            # Original is taller or same aspect ratio as target. Scale by width.
            # New height will be original_h * (target_w / original_w)
            # This new height will be >= target_h.
            scaled_clip = img_clip_initial.resize(width=target_w)

        # At this point, scaled_clip is at least as large as target_dims in one dimension
        # and larger or equal in the other, while maintaining original aspect ratio.

        # Center crop to exact target dimensions
        cropped_clip = crop(scaled_clip,
                              width=target_w, height=target_h,
                              x_center=scaled_clip.w / 2,
                              y_center=scaled_clip.h / 2)

        final_video_frame = cropped_clip.set_duration(duration).set_fps(fps)

        # Wrap in CompositeVideoClip to ensure consistent output type and explicit size.
        # ImageClip itself might not always carry the .size attribute in a way CompositeVideoClip does.
        final_composite = CompositeVideoClip([final_video_frame], size=target_dims).set_duration(duration)

        # Clean up intermediate clips if they are different objects and closable
        if hasattr(img_clip_initial, 'close') and img_clip_initial != final_video_frame : img_clip_initial.close()
        if hasattr(scaled_clip, 'close') and scaled_clip != final_video_frame and scaled_clip != img_clip_initial : scaled_clip.close()
        # cropped_clip is usually the same object as final_video_frame before duration/fps set, or an internal FxApplied
        # if hasattr(cropped_clip, 'close') and cropped_clip != final_video_frame: cropped_clip.close()


        return final_composite

    except Exception as e:
        logger.error(f"Error processing image {image_path}: {e}", exc_info=True)
        if 'img_clip_initial' in locals() and hasattr(img_clip_initial, 'close'): img_clip_initial.close()
        if 'scaled_clip' in locals() and hasattr(scaled_clip, 'close'): scaled_clip.close()
        if 'cropped_clip' in locals() and hasattr(cropped_clip, 'close'): cropped_clip.close()
        if 'final_video_frame' in locals() and hasattr(final_video_frame, 'close'): final_video_frame.close()
        return None

def process_video_clip(
    video_path: str,
    scene_duration: float,
    target_dims: tuple[int, int], # Ensure this is always provided
    target_fps: int # Ensure this is always provided
) -> VideoFileClip | None:
    """
    Loads a video clip, processes it (duration, "cover" resize, center-crop, FPS),
    and returns the processed VideoFileClip object directly.
    The caller is responsible for closing the returned clip's resources using .close().
    The original video file's reader (loaded by this function) is NOT closed here.
    """
    original_clip_loaded = None
    final_transformed_clip = None
    clip_was_extended = False

    try:
        if not pathlib.Path(video_path).exists():
            logger.error(f"Video file not found at {video_path}")
            return None

        original_clip_loaded = VideoFileClip(video_path, audio=True) # Keep audio for now, will be stripped if extended or by assembler

        current_clip_state = original_clip_loaded

        if current_clip_state.duration < scene_duration:
            logger.warning(f"Video at {video_path} (duration {current_clip_state.duration:.2f}s) is shorter than scene duration {scene_duration:.2f}s. Extending last frame.")
            current_clip_state = current_clip_state.set_duration(scene_duration)
            clip_was_extended = True
        else:
            current_clip_state = current_clip_state.subclip(0, scene_duration)

        current_clip_state = current_clip_state.set_duration(scene_duration) # Ensure exact duration

        original_w, original_h = current_clip_state.size
        target_w, target_h = target_dims

        if original_w == 0 or original_h == 0:
            logger.error(f"Video at {video_path} (after duration processing) has zero dimensions.")
            # original_clip_loaded is not closed here; caller of process_video_clip handles returned clip
            return None

        ar_original = original_w / original_h
        ar_target = target_w / target_h

        scaled_clip_for_crop = current_clip_state # Start with current state

        if ar_original > ar_target: # Original is wider than target aspect ratio. Scale by height.
            scaled_clip_for_crop = resize(current_clip_state, height=target_h)
        else: # Original is taller or same aspect ratio as target. Scale by width.
            scaled_clip_for_crop = resize(current_clip_state, width=target_w)

        # Close intermediate clip from resize if it's a new object and different from current_clip_state
        if scaled_clip_for_crop != current_clip_state and hasattr(current_clip_state, 'close'):
            # current_clip_state might be original_clip_loaded or a derivative.
            # If we close original_clip_loaded here, and scaled_clip_for_crop still depends on it, bad.
            # Let's assume resize() returns a new clip that doesn't need the old one open if current_clip_state isn't original_clip_loaded.
            # This area is tricky. For now, let's only close if current_clip_state is NOT original_clip_loaded.
            if current_clip_state != original_clip_loaded:
                 current_clip_state.close()


        cropped_clip = crop(scaled_clip_for_crop,
                               width=target_w, height=target_h,
                               x_center=scaled_clip_for_crop.w / 2,
                               y_center=scaled_clip_for_crop.h / 2)

        # Close intermediate from scaling if it's a new object and different from cropped_clip
        if scaled_clip_for_crop != cropped_clip and hasattr(scaled_clip_for_crop, 'close'):
            scaled_clip_for_crop.close()


        final_transformed_clip = cropped_clip.set_fps(target_fps).set_duration(scene_duration)

        if clip_was_extended:
            logger.info(f"Clip {pathlib.Path(video_path).name} was extended. Its audio is None.")
            final_transformed_clip = final_transformed_clip.set_audio(None) # Ensure audio is None if extended
        elif final_transformed_clip.audio: # If not extended but has audio, log it or remove if unwanted by default
            logger.debug(f"Clip {pathlib.Path(video_path).name} has audio. It will be used unless assembler strips it.")
            # By default, we are keeping audio if not extended. Assembler makes final decision.

        # Close intermediate from cropping if it's new and different from final_transformed_clip
        if cropped_clip != final_transformed_clip and hasattr(cropped_clip, 'close'):
            cropped_clip.close()

        logger.info(f"Processed clip for {pathlib.Path(video_path).name} directly (duration: {final_transformed_clip.duration:.2f}s, FPS: {final_transformed_clip.fps}, Audio: {'No' if final_transformed_clip.audio is None else 'Yes'})")
        return final_transformed_clip

    except Exception as e:
        logger.error(f"Error processing video {video_path}: {e}", exc_info=True)
        # original_clip_loaded is not closed here. The returned clip (None in case of error) is handled by caller.
        # However, if intermediates like scaled_clip_for_crop or cropped_clip were created, try to clean.
        if 'scaled_clip_for_crop' in locals() and hasattr(scaled_clip_for_crop, 'close'): scaled_clip_for_crop.close()
        if 'cropped_clip' in locals() and hasattr(cropped_clip, 'close'): cropped_clip.close()
        return None
    finally:
        # DO NOT CLOSE original_clip_loaded here.
        # The returned final_transformed_clip may still depend on its reader.
        # The caller (video_assembler.py) is responsible for closing the clip returned by this function.
        pass
