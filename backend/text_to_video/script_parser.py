import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_script(script_path: str) -> dict | None:
    """
    Load and parse a JSON script file.

    Args:
        script_path (str): Path to the JSON script file.

    Returns:
        dict | None: Parsed script as a dictionary, or None if error.
    """
    try:
        if not os.path.exists(script_path):
            logger.error(f"Script file not found: {script_path}")
            return None

        with open(script_path, 'r') as f:
            script_data = json.load(f)
        logger.info(f"Successfully parsed script: {script_path}")
        return script_data

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {script_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading script file {script_path}: {e}")
        return None

if __name__ == "__main__":
    logger.info("Testing Script Parser...")
    # Construct path relative to this file's location
    current_dir = os.path.dirname(__file__)
    workspace_root = os.path.abspath(os.path.join(current_dir, '..', '..')) # Go up two levels
    test_script_path = os.path.join(workspace_root, 'public', 'script2.md') # Note: It's .md but contains JSON

    logger.info(f"Attempting to parse: {test_script_path}")

    parsed_data = parse_script(test_script_path)

    if parsed_data:
        print("\nSuccessfully parsed script data:")
        # Print only the top-level keys for brevity
        print(json.dumps(list(parsed_data.keys()), indent=2))
        # Example: Accessing a specific part
        # print(f"\nTitle: {parsed_data.get('video_structure', {}).get('title')}")
    else:
        print("\nFailed to parse script.")
