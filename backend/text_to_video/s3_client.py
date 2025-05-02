import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_s3_client():
    """Creates and returns an S3 client using environment credentials."""
    try:
        # Boto3 will automatically look for credentials in environment variables:
        # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (optional)
        # AWS_DEFAULT_REGION (optional, but good practice)
        s3_client = boto3.client('s3')
        # Test credentials by listing buckets (optional, requires ListBuckets permission)
        # s3_client.list_buckets()
        logger.info("Successfully created S3 client.")
        return s3_client
    except NoCredentialsError:
        logger.error("AWS credentials not found. Ensure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY are set.")
        return None
    except ClientError as e:
        logger.error(f"Error creating S3 client or validating credentials: {e}")
        return None

def ensure_s3_bucket(s3_client, bucket_name: str, region: str = None):
    """
    Checks if an S3 bucket exists, and creates it if it doesn't.

    Args:
        s3_client: An initialized boto3 S3 client.
        bucket_name (str): The name of the bucket.
        region (str, optional): The AWS region for the bucket. Defaults to client's region.
                                Needs to be specified for creation if not us-east-1.

    Returns:
        bool: True if the bucket exists or was created, False otherwise.
    """
    if not s3_client:
        return False
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info(f"S3 bucket '{bucket_name}' already exists.")
        return True
    except ClientError as e:
        # If it doesn't exist, create it
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            logger.info(f"S3 bucket '{bucket_name}' not found. Attempting to create...")
            try:
                if region and region != 'us-east-1':
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': region}
                    )
                else:
                    # No CreateBucketConfiguration needed for us-east-1
                    s3_client.create_bucket(Bucket=bucket_name)

                # Optional: Add a public read ACL if needed for direct HeyGen access
                # Note: Making buckets/objects public has security implications.
                # Consider using signed URLs if possible, although HeyGen might not support them.
                # s3_client.put_bucket_acl(Bucket=bucket_name, ACL='public-read')
                logger.info(f"Successfully created S3 bucket '{bucket_name}' in region '{region or 'us-east-1'}'.")
                # Consider adding a bucket policy for public read on objects if ACLs disabled
                return True
            except ClientError as creation_error:
                logger.error(f"Failed to create S3 bucket '{bucket_name}': {creation_error}")
                return False
            except Exception as creation_e:
                 logger.error(f"An unexpected error occurred during bucket creation: {creation_e}")
                 return False
        else:
            logger.error(f"Error checking S3 bucket '{bucket_name}': {e}")
            return False

def upload_to_s3(s3_client, local_file_path: str, bucket_name: str, s3_key: str) -> str | None:
    """
    Uploads a local file to an S3 bucket and returns its public URL.

    Args:
        s3_client: An initialized boto3 S3 client.
        local_file_path (str): The path to the local file to upload.
        bucket_name (str): The name of the target S3 bucket.
        s3_key (str): The desired key (path/filename) for the object in S3.

    Returns:
        str | None: The public URL of the uploaded object, or None if upload failed.
                    Note: URL format depends on region and bucket settings.
                    Assumes bucket allows public read for this URL to work directly.
    """
    if not s3_client:
        return None
    if not os.path.exists(local_file_path):
        logger.error(f"Local file not found for upload: {local_file_path}")
        return None

    try:
        logger.info(f"Uploading {local_file_path} to s3://{bucket_name}/{s3_key}")
        s3_client.upload_file(
            local_file_path,
            bucket_name,
            s3_key,
            # Set ACL to public-read if needed for direct URL access by HeyGen
            # This depends on your bucket ACL settings.
            # ExtraArgs={'ACL': 'public-read', 'ContentType': 'audio/mpeg'} # Assuming MP3
            # Removed ACL setting as bucket does not support it.
            ExtraArgs={'ContentType': 'audio/mpeg'} # Set only ContentType
        )

        # Construct the public URL (common format, may vary slightly by region/settings)
        region = s3_client.meta.region_name
        if region == 'us-east-1':
            object_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        else:
            object_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"

        logger.info(f"Successfully uploaded to {object_url}")
        return object_url

    except ClientError as e:
        logger.error(f"Failed to upload {local_file_path} to S3: {e}")
        return None
    except NoCredentialsError:
        logger.error("AWS credentials not found during upload.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during S3 upload: {e}")
        return None

# Example Usage
if __name__ == "__main__":
    load_dotenv()
    TEST_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "my-heygen-audio-test-bucket-unique")
    TEST_REGION = os.getenv("AWS_DEFAULT_REGION") # Use default region from env

    print(f"Testing S3 Client with bucket: {TEST_BUCKET_NAME} in region: {TEST_REGION}")

    s3 = get_s3_client()

    if s3:
        # 1. Ensure bucket exists
        print("\n1. Ensuring bucket exists...")
        bucket_ok = ensure_s3_bucket(s3, TEST_BUCKET_NAME, region=TEST_REGION)
        if not bucket_ok:
            print("Halting test due to bucket issue.")
            exit()
        print("Bucket check/creation successful.")

        # 2. Create a dummy local file for upload
        print("\n2. Creating dummy file...")
        dummy_file = "dummy_audio.mp3"
        try:
            with open(dummy_file, "w") as f:
                f.write("This is dummy audio content.")
            print(f"Created dummy file: {dummy_file}")
        except Exception as e:
            print(f"Failed to create dummy file: {e}")
            exit()

        # 3. Upload the dummy file
        print("\n3. Uploading dummy file...")
        s3_object_key = f"test_uploads/{dummy_file}"
        public_url = upload_to_s3(s3, dummy_file, TEST_BUCKET_NAME, s3_object_key)

        if public_url:
            print(f"Upload successful. Public URL: {public_url}")
            # You can try accessing this URL in a browser (requires public read)
        else:
            print("Upload failed.")

        # 4. Clean up dummy file
        print("\n4. Cleaning up dummy file...")
        if os.path.exists(dummy_file):
            os.remove(dummy_file)
            print(f"Removed dummy file: {dummy_file}")
    else:
        print("Could not initialize S3 client. Check credentials and AWS setup.")

    print("\nS3 client test finished.")
