import argparse
import os
import json
import yaml
import logging
import pathlib
import shutil
import re
import datetime
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

# Import necessary modules from the pipeline
from backend.text_to_video.tts import text_to_speech, sanitize_filename
from backend.text_to_video.fx.transcriber import transcribe_locally
from backend.text_to_video.llm_clients.claude_client import ClaudeClient

# Import refactored orchestrator and assembler
from backend.video_pipeline.asset_orchestrator import run_asset_orchestration
from backend.video_pipeline.video_assembler import assemble_final_video

# --- Configuration ---
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VideoPipelineRun")
load_dotenv(PROJECT_ROOT / ".env")

CONFIG_FILE_PATH = PROJECT_ROOT / "backend" / "tests" / "test_config.yaml" # Using test_config for now
TECH_IN_ASIA_SCRIPT_PROMPT_PATH = PROJECT_ROOT / "config" / "tech_in_asia_script_prompt.md"
VISUAL_SCENE_PLANNER_PROMPT_PATH = PROJECT_ROOT / "backend" / "prompts" / "visual_scene_planner_prompt_template.md"
DEFAULT_OUTPUT_BASE_DIR = PROJECT_ROOT / "video_outputs"

def load_pipeline_config():
    if not CONFIG_FILE_PATH.exists():
        logger.error(f"Config file not found at {CONFIG_FILE_PATH}")
        raise FileNotFoundError(f"Config file not found at {CONFIG_FILE_PATH}")
    with open(CONFIG_FILE_PATH, 'r') as f:
        return yaml.safe_load(f)

def get_prompt_template(template_path: pathlib.Path) -> str:
    if not template_path.exists():
        logger.error(f"Prompt template file not found at {template_path}")
        raise FileNotFoundError(f"Prompt template file not found at {template_path}")
    with open(template_path, 'r') as f:
        return f.read()

def generate_video_script(story_content: str, claude_client: ClaudeClient, config: dict, output_dir: pathlib.Path) -> pathlib.Path:
    logger.info("--- Step 1: Generating Video Script ---")
    script_prompt_template = get_prompt_template(TECH_IN_ASIA_SCRIPT_PROMPT_PATH)

    system_prompt = "You are an expert video script writer for Tech in Asia. Follow the user's instructions precisely and return only the JSON object."
    # Append story_content to the prompt (assuming template is designed for this)
    user_prompt = script_prompt_template + f"\n\n<article_content>\n{story_content}\n</article_content>"

    llm_config = config.get('llm_script_writer', config.get('llm_scene_planner', {}))

    call_params = {}
    max_tokens_config = llm_config.get("MAX_TOKENS")
    if max_tokens_config is not None:
        call_params['max_tokens'] = int(max_tokens_config)

    temperature_config = llm_config.get("TEMPERATURE")
    if temperature_config is not None:
        call_params['temperature'] = float(temperature_config)

    # Use generate_structured_output as it expects JSON
    script_data = claude_client.generate_structured_output(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        **call_params
    )

    if not script_data:
        # generate_structured_output logs errors internally, but we raise here to stop the pipeline.
        raise ValueError("LLM response for script generation was None, empty, or failed to parse as JSON.")

    # script_data is already a parsed dict or list if successful
    # No need for re.search or json.loads here anymore if generate_structured_output handles it

    script_output_path = output_dir / "01_generated_video_script.json"
    with open(script_output_path, 'w') as f:
        json.dump(script_data, f, indent=2)
    logger.info(f"Generated video script saved to: {script_output_path}")
    return script_output_path

def generate_tts_audio(script_data: dict, config: dict, output_dir: pathlib.Path) -> pathlib.Path:
    logger.info("--- Step 2: Generating TTS Audio ---")
    full_voiceover_text = " ".join(
        segment["voiceover"]
        for segment_key in ["hook", "conflict", "body", "conclusion"]
        if (segment := script_data.get("script_segments", {}).get(segment_key)) and "voiceover" in segment
    ).strip()

    if not full_voiceover_text:
        raise ValueError("Could not extract voiceover text from script.")

    tts_config = config.get("tts_settings", {})
    script_title = script_data.get("video_structure", {}).get("title", "video_run")
    tts_output_filename = sanitize_filename(f"{script_title}_master_vo.mp3")

    # elevenlabs.tts saves to its own default if output_path is just a filename
    # Let's ensure it saves directly to our desired output_dir
    temp_tts_save_dir = PROJECT_ROOT / "backend" / "assets" / "audio" / "speech"
    temp_tts_save_dir.mkdir(parents=True, exist_ok=True)

    generated_audio_path_str = text_to_speech(
        text=full_voiceover_text,
        output_filename=tts_output_filename, # This will be relative to the default save dir of text_to_speech
        voice_id=tts_config.get("VOICE_ID"),
        model_id=tts_config.get("MODEL_ID"),
        speed=float(tts_config.get("SPEED", 1.0)),
        # Add other params from config as needed
    )
    if not generated_audio_path_str:
        raise RuntimeError("TTS generation failed.")

    # Move to final output directory
    source_audio_path = pathlib.Path(generated_audio_path_str) # This is path where tts.py saved it
    final_audio_path = output_dir / source_audio_path.name # Ensure we use the same filename
    shutil.move(str(source_audio_path), str(final_audio_path))

    logger.info(f"TTS audio saved to: {final_audio_path}")
    return final_audio_path

def generate_transcription(audio_path: pathlib.Path, output_dir: pathlib.Path) -> pathlib.Path:
    logger.info("--- Step 3: Generating Transcription ---")
    transcription_segments = transcribe_locally(str(audio_path))
    if not transcription_segments:
        raise RuntimeError("Transcription failed.")

    word_level_transcript = []
    if transcription_segments and isinstance(transcription_segments, list) and len(transcription_segments) > 0 and 'words' in transcription_segments[0]:
        for segment in transcription_segments:
            word_level_transcript.extend(segment['words'])
    else: # Fallback if format is different (e.g. list of segments without 'words' key)
        logger.warning("Transcription segments in unexpected format. Attempting fallback extraction.")
        for seg_idx, segment in enumerate(transcription_segments if isinstance(transcription_segments, list) else []):
            if not isinstance(segment, dict): continue
            text = segment.get('text', '').strip()
            start_time = segment.get('start', seg_idx * 2.0) # Approximate start
            end_time = segment.get('end', start_time + len(text.split()) * 0.5) # Approximate end
            words_in_segment = text.split()
            num_words = len(words_in_segment)
            approx_duration_per_word = (end_time - start_time) / num_words if num_words > 0 else 0
            current_word_time = start_time
            for word_text in words_in_segment:
                word_level_transcript.append({
                    "word": word_text,
                    "start": round(current_word_time, 3),
                    "end": round(current_word_time + approx_duration_per_word, 3),
                })
                current_word_time += approx_duration_per_word

    if not word_level_transcript:
        raise ValueError("Transcription did not yield any word-level data.")

    transcription_output_path = output_dir / "03_transcription.json"
    with open(transcription_output_path, 'w') as f:
        json.dump(word_level_transcript, f, indent=2)
    logger.info(f"Transcription saved to: {transcription_output_path}")
    return transcription_output_path

def generate_scene_plan(script_data_path: pathlib.Path, transcript_path: pathlib.Path, claude_client: ClaudeClient, config: dict, output_dir: pathlib.Path) -> pathlib.Path:
    logger.info("--- Step 4: Generating Scene Plan ---")
    with open(script_data_path, 'r') as f: script_data = json.load(f)
    with open(transcript_path, 'r') as f: word_transcript = json.load(f)

    scene_planner_prompt_template = get_prompt_template(VISUAL_SCENE_PLANNER_PROMPT_PATH)
    llm_config = config['llm_scene_planner'].copy() # Use a copy to safely modify
    system_prompt = "You are an expert video production planner. Follow instructions precisely and return only the JSON list."

    # Prepare a version of llm_config for the prompt that EXCLUDES specific call parameters
    # These are handled by call_params directly to allow API defaults if not set.
    config_for_prompt = llm_config.copy()
    config_for_prompt.pop("MAX_TOKENS", None)
    config_for_prompt.pop("TEMPERATURE", None)
    config_for_prompt.pop("MODEL_NAME", None) # Also remove MODEL_NAME as it's not for the prompt content

    replacements = {
        "{{word_transcript_json_string}}": json.dumps(word_transcript),
        "{{script_json_string}}": json.dumps(script_data),
        "{{min_segment_duration}}": str(llm_config["MIN_SEGMENT_DURATION"]),
        "{{max_segment_duration}}": str(llm_config["MAX_SEGMENT_DURATION"]),
        "{{photo_segment_threshold}}": str(llm_config["PHOTO_SEGMENT_THRESHOLD"]),
        "{{max_keywords_per_scene}}": str(llm_config["MAX_KEYWORDS_PER_SCENE"]),
        "{{avatar_scene_preference}}": llm_config["AVATAR_SCENE_PREFERENCE"],
        "{{config_json_string}}": json.dumps(config_for_prompt) # Use the filtered config for the prompt
    }
    user_prompt = scene_planner_prompt_template
    for placeholder, value in replacements.items():
        user_prompt = user_prompt.replace(placeholder, value)

    call_params = {}
    max_tokens_config = llm_config.get("MAX_TOKENS") # Get from original llm_config
    if max_tokens_config is not None:
        call_params['max_tokens'] = int(max_tokens_config)

    temperature_config = llm_config.get("TEMPERATURE") # Get from original llm_config
    if temperature_config is not None:
        call_params['temperature'] = float(temperature_config)

    scene_plans_raw = claude_client.generate_structured_output( # Expects JSON list
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        **call_params
    )
    if not scene_plans_raw:
        raise ValueError("LLM response for scene plan generation was None or empty.")

    scene_plan_output_path = output_dir / "04_scene_plan.json"
    with open(scene_plan_output_path, 'w') as f:
        json.dump(scene_plans_raw, f, indent=2)
    logger.info(f"Scene plan saved to: {scene_plan_output_path}")
    return scene_plan_output_path

def main():
    parser = argparse.ArgumentParser(description="Run the full video generation pipeline.")
    parser.add_argument("input_source", type=str, help="Path to a Markdown file or raw story text.")
    parser.add_argument("--output_dir", type=str, help="Optional: Directory to save outputs. Defaults to a timestamped dir in ./video_outputs.")
    args = parser.parse_args()

    config = load_pipeline_config()

    # Determine input type and content
    story_content = ""
    input_path = pathlib.Path(args.input_source)
    input_name_stem = "pipeline_run"
    if input_path.is_file() and input_path.suffix.lower() == ".md":
        logger.info(f"Loading story from Markdown file: {args.input_source}")
        with open(input_path, 'r', encoding='utf-8') as f:
            story_content = f.read()
        input_name_stem = input_path.stem
    elif os.path.exists(args.input_source) and not input_path.is_file():
         logger.error(f"Input source '{args.input_source}' exists but is not a file. Please provide a valid .md file or raw text.")
         sys.exit(1)
    else:
        logger.info("Using raw text as story input.")
        story_content = args.input_source
        # For raw text, create a generic stem or hash for the output folder name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        input_name_stem = f"text_input_{timestamp}"


    if not story_content.strip():
        logger.error("Input story content is empty.")
        sys.exit(1)

    # Setup output directory
    if args.output_dir:
        output_dir = pathlib.Path(args.output_dir)
    else:
        DEFAULT_OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
        output_dir = DEFAULT_OUTPUT_BASE_DIR / input_name_stem

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Pipeline outputs will be saved to: {output_dir}")

    # Initialize Claude client
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY not found in environment variables.")
        sys.exit(1)

    llm_planner_config = config.get('llm_scene_planner', {})
    claude_model = llm_planner_config.get("MODEL_NAME", "claude-3-5-sonnet-20240620")
    claude_client = ClaudeClient(model=claude_model)

    try:
        # --- Run Pipeline Steps ---
        script_path = generate_video_script(story_content, claude_client, config, output_dir)

        with open(script_path, 'r') as f:
            script_data_for_tts = json.load(f)
        audio_path = generate_tts_audio(script_data_for_tts, config, output_dir)

        transcript_path = generate_transcription(audio_path, output_dir)

        scene_plan_path = generate_scene_plan(script_path, transcript_path, claude_client, config, output_dir)

        logger.info(f"--- Step 5: Asset Orchestration ---")
        orchestration_summary_path = run_asset_orchestration(
            scene_plan_path_str=str(scene_plan_path),
            master_vo_path_str=str(audio_path),
            original_script_path_str=str(script_path), # The JSON script from step 1
            output_dir=output_dir,
            # pipeline_config=config # Pass full config if orchestrator needs more than env vars
        )
        logger.info(f"Asset orchestration summary saved to: {orchestration_summary_path}")

        logger.info(f"--- Step 6: Video Assembly ---")
        video_general_config = config.get("video_general", {})
        target_fps = video_general_config.get("TARGET_FPS", 30)
        target_dims = tuple(video_general_config.get("TARGET_DIMENSIONS", [1080, 1920]))
        if len(target_dims) != 2: target_dims = (1080, 1920) # Fallback

        final_video_filename = f"{input_name_stem}_final_video.mp4"
        final_video_path = assemble_final_video(
            orchestration_summary_path_str=str(orchestration_summary_path),
            transcription_path_str=str(transcript_path),
            final_output_dir=output_dir,
            final_video_filename=final_video_filename,
            target_fps=target_fps,
            target_dims=target_dims
        )
        if final_video_path:
            logger.info(f"Final video generated: {final_video_path}")
        else:
            raise RuntimeError("Video assembly failed to produce a final video path.")

        logger.info("--- Pipeline Execution Completed Successfully! ---")
        logger.info(f"Outputs are in: {output_dir}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
