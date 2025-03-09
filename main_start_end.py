import os
import csv
import json
import argparse
import subprocess
import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs


def read_timestamps_from_file(filename):
    """
    Read timestamps from a text file and return them as a list of datetime objects.
    Each line in the file should contain a timestamp.
    """
    timestamps = []

    try:
        with open(filename, "r") as file:
            for line in file:
                # Strip whitespace and skip empty lines
                line = line.strip()
                if not line:
                    continue

                try:
                    # Attempt to parse the timestamp
                    # Assuming format like: "2023-12-31 23:59:59"
                    # You may need to adjust the format based on your actual timestamps
                    timestamp = datetime.datetime.strptime(line, "%Y-%m-%d %H:%M:%S")
                    timestamps.append(timestamp)
                except ValueError as e:
                    print(f"Warning: Could not parse timestamp '{line}': {e}")

        return timestamps

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []


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
def download_vod(url, output_dir, quality, start_time=None, end_time=None):
    """Download a single VOD with the specified parameters."""
    # Base command
    cmd = ["yt-dlp", "-o", f"{output_dir}/%(title)s.%(ext)s"]

    # Add quality parameter
    if quality:
        cmd.extend(["-f", quality])

    # Add time parameters if provided
    if start_time:
        cmd.extend(["--download-sections", f"*{start_time}"])
        if end_time:
            cmd[-1] += f"-{end_time}"

    # Add the URL
    cmd.append(url)

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Download failed: {result.stderr}")

    return url


# Function to process a list of VODs
def batch_process(
    urls_file, output_dir, workers, quality, default_start=None, default_end=None
):
    """Process multiple VOD downloads from a file."""
    os.makedirs(output_dir, exist_ok=True)

    download_tasks = []

    # Read the URLs file
    with open(urls_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):  # Skip empty lines and comments
                continue

            # Parse line: URL [START_TIME] [END_TIME]
            parts = line.split()
            url = parts[0]

            # Extract timestamps if provided in the file
            start_time = parts[1] if len(parts) > 1 else default_start
            end_time = parts[2] if len(parts) > 2 else default_end

            download_tasks.append((url, output_dir, quality, start_time, end_time))

    print(f"Preparing to download {len(download_tasks)} VODs with {workers} workers")

    # Create a pool of workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit download tasks
        futures = [
            executor.submit(
                download_vod, url, output_dir, quality, start_time, end_time
            )
            for url, output_dir, quality, start_time, end_time in download_tasks
        ]

        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                print(f"Completed: {result}")
            except Exception as e:
                print(f"Error during download: {e}")


def main():
    parser = argparse.ArgumentParser(description="Download Twitch VODs efficiently")
    parser.add_argument(
        "urls_file",
        help="Text file containing Twitch VOD URLs with optional timestamps (format: URL [START_TIME] [END_TIME])",
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
        default="best",
        help="Video quality (best, worst, 720p, etc.)",
    )
    parser.add_argument(
        "--start" "-s",
        help="Default start time if not specified in file (format: HH:MM:SS)",
    )
    parser.add_argument(
        "--end",
        "-e",
        help="Default end time if not specified in file (format: HH:MM:SS)",
    )
    args = parser.parse_args()

    # Check for yt-dlp
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True)
    except FileNotFoundError:
        print("Error: yt-dlp is not installed. Please install it using:")
        print("pip install yt-dlp")
        return

    # Update batch_process call to include new parameters
    batch_process(
        args.urls_file, args.output, args.workers, args.quality, args.start, args.end
    )


if __name__ == "__main__":
    main()
