from moviepy.editor import TextClip, CompositeVideoClip, ColorClip
import os # Add os import for path joining

def animate_text_fade(
    text_content: str,
    total_duration: float,
    screen_size: tuple[int, int],
    font_props: dict = None,
    position: tuple[str | int, str | int] = ('center', 'center'),
    fadein_duration: float = 1.0,
    fadeout_duration: float = 1.0,
    bg_color: tuple[int, int, int] = (0, 0, 0),
    is_transparent: bool = True
) -> CompositeVideoClip:
    """
    Creates a text animation that fades in, holds, and fades out.

    Args:
        text_content: The text to be animated.
        total_duration: The total duration the text effect should last on screen.
        screen_size: A tuple (width, height) of the screen.
        font_props: A dictionary for TextClip font properties
                    (e.g., {'font': 'Arial', 'fontsize': 70, 'color': 'yellow'}).
        position: Position of the text on the screen. Can be keywords or (x,y) tuple.
        fadein_duration: Duration of the fade-in effect.
        fadeout_duration: Duration of the fade-out effect.
        bg_color: Background color for the ColorClip if not transparent.
        is_transparent: If True, the ColorClip background will be transparent (mask).

    Returns:
        A CompositeVideoClip containing the fading text animation.
    """
    default_font_path = os.path.join(os.path.dirname(__file__), '../../../assets/fonts/PoetsenOne-Regular.ttf')
    if font_props is None:
        font_props = {'font': default_font_path, 'fontsize': 100, 'color': 'white', 'stroke_color': 'black', 'stroke_width': 2}
    else: # Ensure defaults are applied if not provided
        font_props.setdefault('font', default_font_path)
        font_props.setdefault('fontsize', 100)
        font_props.setdefault('color', 'white')
        font_props.setdefault('stroke_color', 'black')
        font_props.setdefault('stroke_width', 2)

    # Handle position adjustments
    pos_x, pos_y = position
    if isinstance(pos_y, str) and pos_y.lower() == 'bottom':
        raise ValueError("Bottom placement is reserved for captions and not allowed for text animations.")
    if isinstance(pos_y, str) and pos_y.lower() == 'top':
        pos_y = 50 # Apply padding

    # Ensure x is centered if only y is specified as a keyword (e.g. 'top')
    if isinstance(pos_x, str) and pos_x.lower() == 'center' and isinstance(pos_y, int):
        final_position = ('center', pos_y)
    elif isinstance(pos_y, str) and pos_y.lower() == 'center' and isinstance(pos_x, int):
        final_position = (pos_x, 'center')
    else:
        final_position = (pos_x, pos_y)

    if fadein_duration + fadeout_duration > total_duration:
        # Adjust fades if they are too long relative to total_duration
        if total_duration > 0:
            ratio = total_duration / (fadein_duration + fadeout_duration)
            fadein_duration *= ratio
            fadeout_duration *= ratio
        else: # Avoid division by zero if total_duration is 0
            fadein_duration = 0
            fadeout_duration = 0
        print(f"Warning: Fade durations potentially exceeded total_duration. Adjusted to: {fadein_duration:.2f}s in, {fadeout_duration:.2f}s out for total {total_duration:.2f}s.")

    # Create the base TextClip. If is_transparent, bg_color for TextClip itself is not set.
    # MoviePy's TextClip default bg_color is transparent.
    actual_font_props = font_props.copy()
    if not is_transparent and 'bg_color' not in actual_font_props: # only add solid bg to textclip if needed
        pass # TextClip will be on a solid background_clip later

    text_clip = TextClip(text_content, **actual_font_props)
    text_clip = text_clip.set_position(final_position) # Use adjusted position
    text_clip_effect = text_clip.set_duration(total_duration)

    if fadein_duration > 0:
        text_clip_effect = text_clip_effect.crossfadein(fadein_duration)
    if fadeout_duration > 0:
        text_clip_effect = text_clip_effect.crossfadeout(fadeout_duration)

    if is_transparent:
        # For a transparent effect, the text_clip_effect itself (with its alpha) is primary.
        # We wrap it in a CompositeVideoClip to ensure it conforms to screen_size.
        # The background of this CompositeVideoClip will be implicitly transparent.
        final_animation = CompositeVideoClip([text_clip_effect], size=screen_size)
    else:
        background_clip = ColorClip(size=screen_size, color=bg_color, duration=total_duration)
        final_animation = CompositeVideoClip([background_clip, text_clip_effect], size=screen_size, use_bgclip=True)

    return final_animation

def animate_text_scale(
    text_content: str,
    total_duration: float,
    screen_size: tuple[int, int],
    font_props: dict = None,
    start_scale: float = 1.0,
    end_scale: float = 2.0,
    position: tuple[str | int, str | int] = ('center', 'center'),
    bg_color: tuple[int, int, int] = (0, 0, 0),
    is_transparent: bool = True,
    apply_fade: bool = True,
    fade_proportion: float = 0.2
) -> CompositeVideoClip:
    """
    Creates a text animation that scales over time, centered on the screen.
    Optionally applies a fade in/out effect concurrent with scaling.

    Args:
        text_content: The text to be animated.
        total_duration: The total duration the text effect should last on screen.
        screen_size: A tuple (width, height) of the screen.
        font_props: Dictionary for TextClip font properties.
        start_scale: The initial scaling factor of the text.
        end_scale: The final scaling factor of the text.
        bg_color: Background color if not transparent.
        is_transparent: If True, background is transparent.
        apply_fade: If True, applies a fade-in and fade-out effect during the scaling.
        fade_proportion: Proportion of total_duration for each fade effect (if apply_fade).

    Returns:
        A CompositeVideoClip containing the scaling text animation.
    """
    default_font_path = os.path.join(os.path.dirname(__file__), '../../../assets/fonts/PoetsenOne-Regular.ttf')
    if font_props is None:
        font_props = {'font': default_font_path, 'fontsize': 100, 'color': 'white', 'stroke_color': 'black', 'stroke_width': 2}
    else: # Ensure defaults are applied if not provided
        font_props.setdefault('font', default_font_path)
        font_props.setdefault('fontsize', 100)
        font_props.setdefault('color', 'white')
        font_props.setdefault('stroke_color', 'black')
        font_props.setdefault('stroke_width', 2)

    screen_w, screen_h = screen_size

    # Handle position adjustments for scaling
    pos_x_in, pos_y_in = position
    if isinstance(pos_y_in, str) and pos_y_in.lower() == 'bottom':
        raise ValueError("Bottom placement is reserved for captions and not allowed for text animations.")

    # Create TextClip. If transparent, its own background is transparent.
    base_text_clip = TextClip(text_content, **font_props)
    text_w, text_h = base_text_clip.size # Get original size for centering calculation

    def resize_func(t):
        current_scale = start_scale + (t / total_duration) * (end_scale - start_scale) if total_duration > 0 else start_scale
        return current_scale

    def position_func_centered(t):
        current_scale = resize_func(t)
        # Resolve initial position
        current_x, current_y = pos_x_in, pos_y_in

        if isinstance(current_x, str) and current_x.lower() == 'center':
            x = (screen_w - text_w * current_scale) / 2
        else:
            x = current_x # Assume numeric if not 'center'

        if isinstance(current_y, str) and current_y.lower() == 'center':
            y = (screen_h - text_h * current_scale) / 2
        elif isinstance(current_y, str) and current_y.lower() == 'top':
            y = 50 # Apply padding for top
        else:
            y = current_y # Assume numeric if not 'center' or 'top'

        # Adjust for scaling if centered, otherwise keep fixed position (scaling from top-left of text)
        if isinstance(pos_x_in, str) and pos_x_in.lower() == 'center':
             x_final = (screen_w - text_w * current_scale) / 2
        else: # if x is a number, it's an absolute position
             x_final = pos_x_in

        if isinstance(pos_y_in, str) and pos_y_in.lower() == 'center':
            y_final = (screen_h - text_h * current_scale) / 2
        elif isinstance(pos_y_in, str) and pos_y_in.lower() == 'top':
            y_final = 50 # Apply padding for top
        else: # if y is a number, it's an absolute position
            y_final = pos_y_in

        return (x_final, y_final)

    # Animated text clip (scaling and dynamic centering)
    # Recreate the TextClip here to apply .resize and .set_position that take functions.
    text_clip_animated = (
        TextClip(text_content, **font_props) # Use original font_props for consistent rendering
        .set_duration(total_duration)
        .resize(resize_func)
        .set_position(position_func_centered)
    )

    if apply_fade and total_duration > 0:
        fade_duration = total_duration * fade_proportion
        # Ensure individual fade_duration is not more than half of total_duration
        if fade_duration * 2 > total_duration:
            fade_duration = total_duration / 2

        if fade_duration > 0: # Only apply if fade_duration is positive
            text_clip_animated = text_clip_animated.crossfadein(fade_duration)
            text_clip_animated = text_clip_animated.crossfadeout(fade_duration)

    if is_transparent:
        # For transparent output, the animated text clip is the content.
        # CompositeVideoClip ensures it has the correct screen_size.
        final_animation = CompositeVideoClip([text_clip_animated], size=screen_size)
    else:
        background_clip = ColorClip(size=screen_size, color=bg_color, duration=total_duration)
        final_animation = CompositeVideoClip([background_clip, text_clip_animated], size=screen_size, use_bgclip=True)

    return final_animation

if __name__ == '__main__':
    width, height = 1920, 1080
    output_dir = "./temp_video_outputs"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("Testing animate_text_fade...")
    effect1_duration = 4.0
    fade_animation_transparent = animate_text_fade(
        text_content="Fade Top Padded",
        total_duration=effect1_duration,
        screen_size=(width, height),
        fadein_duration=1.0,
        fadeout_duration=1.0,
        position=('center', 'top'), # Test top padding
        is_transparent=True,
    )
    if fade_animation_transparent.duration > 0 : fade_animation_transparent.write_videofile(os.path.join(output_dir, "effect_fade_transparent_top.mp4"), fps=30, logger=None)
    print(f"Created fade_animation (transparent, top). Duration: {fade_animation_transparent.duration}s.")

    fade_animation_solid = animate_text_fade(
        text_content="Fade Solid Center",
        total_duration=effect1_duration,
        screen_size=(width, height),
        fadein_duration=1.0,
        fadeout_duration=1.0,
        is_transparent=False,
    )
    # Test bottom placement error
    try:
        fade_animation_bottom_error = animate_text_fade(
            text_content="Fade Bottom Error",
            total_duration=1.0,
            screen_size=(width, height),
            position=('center', 'bottom')
        )
    except ValueError as e:
        print(f"Caught expected error for bottom placement: {e}")

    if fade_animation_solid.duration > 0 : fade_animation_solid.write_videofile(os.path.join(output_dir, "effect_fade_solid_center.mp4"), fps=30, logger=None)
    print(f"Created fade_animation (solid, center). Duration: {fade_animation_solid.duration}s.")

    print("\nTesting animate_text_scale...")
    effect_scale_up_duration = 3.0
    scale_up_animation_transparent = animate_text_scale(
        text_content="Zoom Top Padded",
        total_duration=effect_scale_up_duration,
        screen_size=(width, height),
        position=('center', 'top'), # Test top padding for scale
        start_scale=0.5,
        end_scale=2.0,
        is_transparent=True,
        apply_fade=True
    )
    if scale_up_animation_transparent.duration > 0 : scale_up_animation_transparent.write_videofile(os.path.join(output_dir, "effect_scale_up_transparent_top.mp4"), fps=30, logger=None)
    print(f"Created scale_up_animation (transparent, top). Duration: {scale_up_animation_transparent.duration}s.")

    scale_up_animation_solid = animate_text_scale(
        text_content="Zoom Solid Center",
        total_duration=effect_scale_up_duration,
        screen_size=(width, height),
        start_scale=0.5,
        end_scale=2.0,
        is_transparent=False,
        apply_fade=True
    )
    # Test bottom placement error for scale
    try:
        scale_animation_bottom_error = animate_text_scale(
            text_content="Scale Bottom Error",
            total_duration=1.0,
            screen_size=(width, height),
            position=('center', 'bottom')
        )
    except ValueError as e:
        print(f"Caught expected error for bottom placement (scale): {e}")

    if scale_up_animation_solid.duration > 0 : scale_up_animation_solid.write_videofile(os.path.join(output_dir, "effect_scale_up_solid_center.mp4"), fps=30, logger=None)
    print(f"Created scale_up_animation (solid, center). Duration: {scale_up_animation_solid.duration}s.")

    # Test with zero duration
    print("\nTesting zero duration...")
    zero_duration_fade = animate_text_fade("ZeroDurFade", 0, (100,100), is_transparent=True)
    print(f"Created zero_duration_fade. Duration: {zero_duration_fade.duration}s.")
    zero_duration_scale = animate_text_scale("ZeroDurScale", 0, (100,100), is_transparent=True)
    print(f"Created zero_duration_scale. Duration: {zero_duration_scale.duration}s.")

    print("\nTesting specific TEXT_OVERLAY_SCALE case (45%)...")
    scene_003_duration = 2.68 # Example: 7.38s (end) - 4.7s (start)
    scale_animation_45_percent = animate_text_scale(
        text_content="45%",
        total_duration=scene_003_duration,
        screen_size=(width, height), # Using 1920x1080 from existing test setup
        position=('center', 'center'),
        # Using default font_props, start_scale=1.0, end_scale=2.0, is_transparent=True, apply_fade=True
    )
    output_filename_45_percent = os.path.join(output_dir, "effect_scale_45_percent.mp4")
    if scale_animation_45_percent.duration > 0:
        scale_animation_45_percent.write_videofile(output_filename_45_percent, fps=30, logger=None)
    print(f"Created scale_animation_45_percent. Duration: {scale_animation_45_percent.duration}s. Output: {output_filename_45_percent}")

    print(f"\nExamples created. Check the '{output_dir}' directory.")
