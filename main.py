import os
import csv
import json
import argparse
import subprocess
import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs


# Function to extract VOD ID from Twitch URL
def extract_vod_id(url):
    parsed_url = urlparse(url)
    if "twitch.tv" in parsed_url.netloc:
        path_parts = parsed_url.path.split("/")
        for i, part in enumerate(path_parts):
            if part == "videos" or part == "video":
                if i + 1 < len(path_parts):
                    return path_parts[i + 1]
    return None


# Function to get VOD metadata using Twitch API
def get_vod_metadata(vod_id, client_id):
    try:
        # Using yt-dlp to extract metadata (no API key needed)
        cmd = ["yt-dlp", "--dump-json", f"https://www.twitch.tv/videos/{vod_id}"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error getting metadata for VOD {vod_id}: {result.stderr}")
            return None

        metadata = json.loads(result.stdout)
        return {
            "title": metadata.get("title", f"Unknown_VOD_{vod_id}"),
            "channel": metadata.get("uploader", "unknown_channel"),
            "date": metadata.get(
                "upload_date", datetime.datetime.now().strftime("%Y%m%d")
            ),
            "duration": metadata.get("duration", 0),
            "url": metadata.get(
                "webpage_url", f"https://www.twitch.tv/videos/{vod_id}"
            ),
        }
    except Exception as e:
        print(f"Error processing VOD {vod_id}: {str(e)}")
        return None


# Function to download a single VOD
def download_vod(vod_url, output_dir, quality="best"):
    vod_id = extract_vod_id(vod_url)
    if not vod_id:
        print(f"Invalid Twitch VOD URL: {vod_url}")
        return False

    # Get metadata
    metadata = get_vod_metadata(vod_id, None)
    if not metadata:
        print(f"Could not retrieve metadata for VOD {vod_id}")
        return False

    # Create filename with date, channel name, and title
    safe_title = "".join(
        [c if c.isalnum() or c in " -_" else "_" for c in metadata["title"]]
    )
    filename = f"{metadata['date']}_{metadata['channel']}_{safe_title}_{vod_id}.mp4"
    output_path = os.path.join(output_dir, filename)

    # Check if file already exists
    if os.path.exists(output_path):
        print(f"VOD already downloaded: {filename}")
        return True

    print(f"Downloading: {metadata['title']} ({vod_id})")

    # Use yt-dlp for downloading (faster than youtube-dl)
    cmd = [
        "yt-dlp",
        "-f",
        quality,
        "-o",
        output_path,
        "--no-part",
        "--no-warnings",
        vod_url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully downloaded: {filename}")
            # Add to records
            with open(
                os.path.join(output_dir, "vod_records.csv"),
                "a",
                newline="",
                encoding="utf-8",
            ) as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        vod_id,
                        metadata["title"],
                        metadata["channel"],
                        metadata["date"],
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        metadata["url"],
                    ]
                )
            return True
        else:
            print(f"Error downloading VOD {vod_id}: {result.stderr}")
            return False
    except Exception as e:
        print(f"Exception while downloading VOD {vod_id}: {str(e)}")
        return False


# Function to process a list of VODs
def batch_process(urls_file, output_dir, max_workers=3, quality="best"):
    os.makedirs(output_dir, exist_ok=True)

    # Create records file if it doesn't exist
    records_path = os.path.join(output_dir, "vod_records.csv")
    if not os.path.exists(records_path):
        with open(records_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["vod_id", "title", "channel", "date", "download_date", "url"]
            )

    # Read URLs
    with open(urls_file, "r") as f:
        urls = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    print(f"Found {len(urls)} VODs to process")

    # Process URLs concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(
            executor.map(lambda url: download_vod(url, output_dir, quality), urls)
        )

    success_count = sum(1 for r in results if r)
    print(f"Downloaded {success_count} out of {len(urls)} VODs")
    return success_count


def main():
    parser = argparse.ArgumentParser(description="Download Twitch VODs efficiently")
    parser.add_argument(
        "urls_file", help="Text file containing Twitch VOD URLs (one per line)"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="./downloads",
        help="Output directory for downloaded VODs",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=3, help="Number of concurrent downloads"
    )
    parser.add_argument(
        "--quality",
        "-q",
        default="720p",
        help="Video quality (best, worst, 720p, etc.)",
    )
    args = parser.parse_args()

    # Check for yt-dlp
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True)
    except FileNotFoundError:
        print("Error: yt-dlp is not installed. Please install it using:")
        print("pip install yt-dlp")
        return

    batch_process(args.urls_file, args.output, args.workers, args.quality)


if __name__ == "__main__":
    main()
