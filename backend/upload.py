import os
import argparse
from typing import Optional
from tiktok_uploader.auth import AuthBackend
from tiktok_uploader.upload import upload_video

def upload_to_tiktok(
    video_path: str,
    title: str = "TECH INDUSTRY UPDATE",
    post_text: str = "🚨 CHIP SMUGGLERS CAUGHT 🚨 We now know who shipped restricted AI chips to DeepSeek - the Chinese company that caused a 17% DROP! 📉 in Nvidia's stock price! Link in bio for the full shocking story! #TechNews #AIWars",
    cookies_path: Optional[str] = None,
    schedule_time: Optional[int] = None
) -> bool:
    """
    Upload a video to TikTok with specified title and post text.

    Args:
        video_path: Path to the video file to upload
        title: Title for the TikTok video
        post_text: Caption text for the TikTok post
        cookies_path: Path to cookies file for TikTok authentication
        schedule_time: Optional timestamp for scheduled posting

    Returns:
        Boolean indicating success of upload
    """
    # Check if video exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file {video_path} not found")

    # Check if cookies file exists if provided
    if cookies_path and not os.path.exists(cookies_path):
        raise FileNotFoundError(f"Cookies file {cookies_path} not found")

    # If no cookies path provided, use default location
    if not cookies_path:
        cookies_path = os.path.expanduser("~/.tiktok_cookies.txt")

    # Check if user is authenticated
    try:
        auth = AuthBackend(cookies=cookies_path)
        if not auth.is_authenticated():
            print("Not authenticated. Please log in to TikTok.")
            auth.authenticate()
    except Exception as e:
        raise ConnectionError(f"Authentication failed: {e}")

    # Look for cover image in the same folder as the video
    video_folder = os.path.dirname(video_path)
    cover_image_path = os.path.join(video_folder, "coverimage.png")

    # Prepare upload parameters
    upload_params = {
        "video": video_path,
        "description": post_text,
        "cookies": cookies_path
    }

    # Add cover image if it exists
    if os.path.exists(cover_image_path):
        upload_params["thumbnail"] = cover_image_path
        print(f"Using cover image: {cover_image_path}")
    else:
        print(f"Cover image not found at {cover_image_path}, using auto-generated thumbnail")

    # Add schedule time if provided
    if schedule_time:
        upload_params["schedule_time"] = schedule_time

    # Add title if provided
    if title:
        upload_params["title"] = title

    # Attempt to upload video
    try:
        result = upload_video(**upload_params)
        if result:
            print(f"Successfully uploaded video to TikTok: {title}")
            return True
        else:
            print("Upload failed")
            return False
    except Exception as e:
        print(f"Error during upload: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload video to TikTok")
    parser.add_argument("--video", default="assets/demo/output.mp4", help="Path to video file")
    parser.add_argument("--title", default="TECH INDUSTRY UPDATE", help="Title for the TikTok video")
    parser.add_argument("--text", default="🚨 CHIP SMUGGLERS CAUGHT 🚨 We now know who shipped restricted AI chips to DeepSeek - the Chinese company that caused a 17% DROP! 📉 in Nvidia's stock price! Link in bio for the full shocking story! #TechNews #AIWars",
                        help="Caption text for the TikTok post")
    parser.add_argument("--cookies", default=None, help="Path to cookies file for TikTok authentication")
    parser.add_argument("--schedule", type=int, default=None, help="Timestamp for scheduled posting")

    args = parser.parse_args()

    try:
        success = upload_to_tiktok(
            video_path=args.video,
            title=args.title,
            post_text=args.text,
            cookies_path=args.cookies,
            schedule_time=args.schedule
        )

        if success:
            print("Video upload completed successfully")
        else:
            print("Video upload failed")
    except Exception as e:
        print(f"Error: {e}")
