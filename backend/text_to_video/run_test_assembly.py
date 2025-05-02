import asyncio
import os
import sys
import json # Import json for better printing if needed
from dotenv import load_dotenv

# Add current dir to path to find modules
sys.path.append(os.path.dirname(__file__))

# Load env vars BEFORE importing modules that use them
# Go up one level to find the .env file potentially
# Assuming .env is in the 'backend' directory based on structure
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
# Or if .env is at the root:
# dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)
print(f"Loaded .env from: {dotenv_path}")


# Now import necessary parts (AFTER load_dotenv)
try:
    # Import the specific function needed
    from heygen_workflow import run_assembly_and_captioning
    # We also need access to the job_data dictionary from main
    # This is awkward due to global state. A better design would pass job_data around.
    # For testing, we try to import it. Ensure main.py defines it globally.
    # NOTE: This import relies on the FastAPI server process having populated job_data
    #       and NOT having been reloaded since then.
    from main import job_data
    print("Successfully imported run_assembly_and_captioning and job_data.")
except ImportError as e:
    print(f"ImportError: {e}. Ensure main.py and heygen_workflow.py are accessible.")
    print("Make sure you run this script from the project root or adjust sys.path.")
    exit(1)
except Exception as e:
     print(f"An unexpected error occurred during import: {e}")
     exit(1)


async def main():
    # !!! This is the specific Job ID from your last successful test run !!!
    job_id_to_test = "heygen_job_3cc94445-2fde-4893-85d7-00c35200af50"
    print(f"Attempting to run assembly for job_id: {job_id_to_test}")

    # Check if job data exists (it should if the main server process populated it)
    if job_id_to_test not in job_data:
        print(f"Error: Job ID {job_id_to_test} not found in job_data.")
        print("Did the workflow run successfully in the main server process *without* reloading?")
        print("Current job_data keys:", list(job_data.keys()))
        return

    # Make sure job_data is populated correctly before calling assembly
    print(f"Job data found for {job_id_to_test}. Proceeding with assembly...")
    # Optional: Print relevant parts of job_data to verify
    # print("Relevant Job Data Snippet:")
    # print(json.dumps(job_data.get(job_id_to_test, {}).get('assets', {}), indent=2))


    await run_assembly_and_captioning(job_id_to_test)

    print(f"Assembly process finished for job {job_id_to_test}. Check logs and output folder.")
    # You can inspect job_data[job_id_to_test] here if needed
    # print("Final Job Data:")
    # print(json.dumps(job_data.get(job_id_to_test, {}), indent=2))


if __name__ == "__main__":
    # Check Python version for asyncio.run compatibility if needed
    # print(f"Python Version: {sys.version}")
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred running the async main function: {e}")
