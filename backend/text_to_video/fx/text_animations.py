from moviepy.editor import TextClip, CompositeVideoClip, ColorClip

def animate_text_fade(
    text_content: str,
    total_duration: float,
    screen_size: tuple[int, int],
    font_props: dict = None,
    position: tuple[str | int, str | int] = ('center', 'center'),
    fadein_duration: float = 1.0,
    fadeout_duration: float = 1.0,
    bg_color: tuple[int, int, int] = (0, 0, 0),
    is_transparent: bool = False
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
    if font_props is None:
        font_props = {'font': 'Arial-Bold', 'fontsize': 70, 'color': 'white'}

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
    text_clip = text_clip.set_position(position)
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
    # position_func: callable = None, # More complex, for now simple center
    bg_color: tuple[int, int, int] = (0, 0, 0),
    is_transparent: bool = False,
    apply_fade: bool = True, # Whether to apply a gentle fade in/out with scaling
    fade_proportion: float = 0.2 # Proportion of total_duration for fade in/out if apply_fade is True
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
    if font_props is None:
        font_props = {'font': 'Arial-Bold', 'fontsize': 70, 'color': 'white'}

    screen_w, screen_h = screen_size

    # Create TextClip. If transparent, its own background is transparent.
    base_text_clip = TextClip(text_content, **font_props)
    text_w, text_h = base_text_clip.size # Get original size for centering calculation

    def resize_func(t):
        current_scale = start_scale + (t / total_duration) * (end_scale - start_scale) if total_duration > 0 else start_scale
        return current_scale

    def position_func_centered(t):
        current_scale = resize_func(t)
        x = (screen_w - text_w * current_scale) / 2
        y = (screen_h - text_h * current_scale) / 2
        return (x, y)

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
    import os
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("Testing animate_text_fade...")
    effect1_duration = 4.0
    fade_animation_transparent = animate_text_fade(
        text_content="Fade Transparent",
        total_duration=effect1_duration,
        screen_size=(width, height),
        fadein_duration=1.0,
        fadeout_duration=1.0,
        font_props={'font': 'Arial-Bold', 'fontsize': 100, 'color': 'cyan'},
        is_transparent=True,
    )
    if fade_animation_transparent.duration > 0 : fade_animation_transparent.write_videofile(os.path.join(output_dir, "effect_fade_transparent.mp4"), fps=30, logger=None)
    print(f"Created fade_animation (transparent). Duration: {fade_animation_transparent.duration}s.")

    fade_animation_solid = animate_text_fade(
        text_content="Fade Solid",
        total_duration=effect1_duration,
        screen_size=(width, height),
        fadein_duration=1.0,
        fadeout_duration=1.0,
        font_props={'font': 'Arial-Bold', 'fontsize': 100, 'color': 'magenta'},
        is_transparent=False,
        bg_color=(30,30,30)
    )
    if fade_animation_solid.duration > 0 : fade_animation_solid.write_videofile(os.path.join(output_dir, "effect_fade_solid.mp4"), fps=30, logger=None)
    print(f"Created fade_animation (solid). Duration: {fade_animation_solid.duration}s.")

    print("\nTesting animate_text_scale...")
    effect_scale_up_duration = 3.0
    scale_up_animation_transparent = animate_text_scale(
        text_content="Zoom Transparent",
        total_duration=effect_scale_up_duration,
        screen_size=(width, height),
        font_props={'font': 'Impact', 'fontsize': 80, 'color': 'yellow'},
        start_scale=0.5,
        end_scale=2.0,
        is_transparent=True,
        apply_fade=True
    )
    if scale_up_animation_transparent.duration > 0 : scale_up_animation_transparent.write_videofile(os.path.join(output_dir, "effect_scale_up_transparent.mp4"), fps=30, logger=None)
    print(f"Created scale_up_animation (transparent). Duration: {scale_up_animation_transparent.duration}s.")

    scale_up_animation_solid = animate_text_scale(
        text_content="Zoom Solid",
        total_duration=effect_scale_up_duration,
        screen_size=(width, height),
        font_props={'font': 'Impact', 'fontsize': 80, 'color': 'lime'},
        start_scale=0.5,
        end_scale=2.0,
        is_transparent=False,
        bg_color=(0, 50, 0),
        apply_fade=True
    )
    if scale_up_animation_solid.duration > 0 : scale_up_animation_solid.write_videofile(os.path.join(output_dir, "effect_scale_up_solid.mp4"), fps=30, logger=None)
    print(f"Created scale_up_animation (solid). Duration: {scale_up_animation_solid.duration}s.")

    # Test with zero duration
    print("\nTesting zero duration...")
    zero_duration_fade = animate_text_fade("ZeroDurFade", 0, (100,100), is_transparent=True)
    print(f"Created zero_duration_fade. Duration: {zero_duration_fade.duration}s.")
    zero_duration_scale = animate_text_scale("ZeroDurScale", 0, (100,100), is_transparent=True)
    print(f"Created zero_duration_scale. Duration: {zero_duration_scale.duration}s.")

    print(f"\nExamples created. Check the '{output_dir}' directory.")
