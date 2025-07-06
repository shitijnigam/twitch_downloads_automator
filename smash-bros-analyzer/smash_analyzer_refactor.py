##

# smash_analyzer.py

import os
import cv2  # OpenCV for video processing
from datetime import date

# import google.generativeai as genai
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
from tqdm import tqdm
import math

# --- Configuration ---

# 1. Load the API key from the .env file
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError(
        "API key not found. Please create a .env file with GOOGLE_API_KEY='your_key'"
    )

# 2. Set the path to your video file
VIDEO_PATH = "../downloads/20250618_Sparg0_Wifi tournament again ___2488888062.mp4"  # <--- MAKE SURE THIS FILENAME MATCHES YOUR VIDEO

# 3. How often to check the video (in seconds).
# A smaller number is more accurate but uses more API calls (and costs more).
# 5 seconds is a good starting point. The VS screen is usually up for at least this long.
SECONDS_BETWEEN_CHECKS = 2.5

# 4. The prompt we will send to the AI for each frame
PROMPT = """
Analyze this image from a Super Smash Bros. Ultimate video.
Is this the 'VS' screen that appears right before a match starts?
The VS screen clearly shows TWO character portraits and their names (with player names indicated at the bottom, and character names at the top).
- If it IS the VS screen, list the player names and characters in the format indicated below
- If it is NOT the VS screen (e.g., it's gameplay, a menu, a character select screen with a lot of characters, or a results screen), please respond with only the word 'NO'.
Response should follow this format: {Player Name} ({Character}) vs. {Player Name} ({Character}) if it's a match, e.g. Sparg0 (Roy) vs. Sonix (Sonic)
"""

# --- Main Program ---


def main():
    """
    Main function to analyze the video.
    """
    print("Configuring Google Gemini AI...")
    # genai.configure(api_key=API_KEY)

    # We use gemini-1.5-flash: it's fast, cheap, and excellent for this task.
    model_name = "gemini-2.5-flash-lite-preview-06-17"
    client = genai.Client(
        api_key=API_KEY,
    )

    print(f"Opening video file: {VIDEO_PATH}...")
    if not os.path.exists(VIDEO_PATH):
        print(f"Error: Video file not found at '{VIDEO_PATH}'")
        return

    # Use OpenCV to open the video
    cap = cv2.VideoCapture(VIDEO_PATH)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps == 0:
        print("Error: Could not read video FPS. Cannot continue.")
        return

    frame_interval = int(fps * SECONDS_BETWEEN_CHECKS)
    total_checks = math.ceil(total_frames / frame_interval)

    print(f"Video Info: {total_frames} frames, {fps:.2f} FPS.")
    print(
        f"Analyzing one frame every {SECONDS_BETWEEN_CHECKS} seconds. Total checks: {total_checks}"
    )

    found_matches = []

    # Use tqdm for a progress bar
    with tqdm(total=total_checks, unit="frame_check") as pbar:
        for i in range(total_checks):
            frame_index = i * frame_interval
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

            ret, frame = cap.read()
            if not ret:
                break  # End of video

            # Convert frame from OpenCV's BGR format to RGB for PIL/Gemini
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)

            try:
                # Send the prompt and the image to the Gemini model
                response = client.models.generate_content(
                    model=model_name,
                    contents=[PROMPT, pil_image],
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_budget=0)
                    ),
                )

                # Clean up the response text
                analysis_result = response.text.strip()

                # Check if the model identified a VS screen
                if "NO" not in analysis_result.upper():
                    timestamp_seconds = frame_index / fps
                    # Format timestamp as HH:MM:SS
                    ts_formatted = "{:02d}:{:02d}:{:02d}".format(
                        int(timestamp_seconds // 3600),
                        int((timestamp_seconds % 3600) // 60),
                        int(timestamp_seconds % 60),
                    )

                    match_info = {
                        "timestamp": ts_formatted,
                        "characters": analysis_result,
                        "seconds": timestamp_seconds,
                    }
                    found_matches.append(match_info)

                    print(
                        f"\n✅ Match Found at {ts_formatted}! Characters: {analysis_result}"
                    )

            except Exception as e:
                print(f"\nAn error occurred while calling the API: {e}")

            pbar.update(1)

    cap.release()  # Release the video file

    # --- Final Report ---
    print("\n\n--- Analysis Complete ---")
    if not found_matches:
        print("No new games were detected.")
    else:
        # De-duplicate results: a VS screen might be caught twice.
        # We'll only keep the first detection if multiple are within 10 seconds of each other.
        final_results = []
        if found_matches:
            final_results.append(found_matches[0])
            for i in range(1, len(found_matches)):
                # If the current match is more than 10s after the last one we added
                if found_matches[i]["seconds"] - final_results[-1]["seconds"] > 10:
                    final_results.append(found_matches[i])

        print(f"Found {len(final_results)} distinct new games:")
        for match in final_results:
            print(
                f"- Timestamp: {match['timestamp']}, Characters: {match['characters']}"
            )

        # --- BEGIN: SAVE TIMESTAMPS TO FILE ---
        try:
            # 1. Generate the filename with today's date
            today_str = date.today().strftime("%Y-%m-%d")
            filename = f"timestamps_{today_str}.txt"

            # Check if the file already exists to decide if we need a separator
            file_exists = os.path.exists(filename)  # <-- ADDED

            # 2. Open the file in append mode ('a'). This will create the file
            #    if it doesn't exist, or add to the end if it does.
            with open(filename, "a", encoding="utf-8") as f:  # <-- CHANGED 'w' to 'a'
                # If the file already has content, add a separator for readability
                if file_exists:
                    f.write("\n")

                # Write a header for this specific analysis run
                f.write(f"--- Analysis for video: {VIDEO_PATH} ---\n")

                # 3. Loop through the final results and write them to the file
                for match in final_results:
                    line = f"{match['timestamp']} - {match['characters']}\n"
                    f.write(line)

            print(f"\n✅ Successfully appended results to '{filename}'")

        except IOError as e:
            print(f"\n❌ Error: Could not write to file. Reason: {e}")
        # --- END: SAVE TIMESTAMPS TO FILE ---


if __name__ == "__main__":
    main()
