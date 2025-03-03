import os
import time
import json
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def login_to_twitch(driver, username, password):
    """Log in to Twitch"""
    driver.get("https://www.twitch.tv/login")
    time.sleep(2)  # Wait for page to load

    try:
        # Enter username
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "login-username"))
        )
        username_field.send_keys(username)

        # Enter password
        password_field = driver.find_element(By.ID, "password-input")
        password_field.send_keys(password)

        # Click login button
        login_button = driver.find_element(
            By.CSS_SELECTOR, "button[data-a-target='passport-login-button']"
        )
        login_button.click()

        # Wait for login to complete
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".top-nav__menu"))
        )
        print("Successfully logged in to Twitch")
        return True
    except Exception as e:
        print(f"Login failed: {str(e)}")
        return False


def extract_vods_from_following(driver, max_channels=50, max_vods_per_channel=5):
    """Extract VOD links from channels you follow"""
    print("Navigating to Following page...")
    driver.get("https://www.twitch.tv/directory/following")
    time.sleep(3)  # Wait for page to load

    all_vod_links = []

    try:
        # Find followed channels
        channels = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "a[data-a-target='preview-card-channel-link']")
            )
        )

        channel_links = []
        for channel in channels[:max_channels]:
            channel_url = channel.get_attribute("href")
            channel_name = channel_url.split("/")[-1]
            channel_links.append((channel_name, channel_url))

        print(f"Found {len(channel_links)} followed channels")

        # Visit each channel page and extract VODs
        for channel_name, channel_url in channel_links:
            vod_page_url = f"{channel_url}/videos?filter=archives&sort=time"
            print(f"Checking VODs for {channel_name}...")
            driver.get(vod_page_url)
            time.sleep(3)  # Wait for VODs to load

            try:
                vod_links = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "a[data-a-target='preview-card-image-link']")
                    )
                )

                for vod in vod_links[:max_vods_per_channel]:
                    vod_url = vod.get_attribute("href")
                    if "/videos/" in vod_url:
                        all_vod_links.append(vod_url)
                        print(f"  - Found VOD: {vod_url}")
            except Exception as e:
                print(f"  Error extracting VODs from {channel_name}: {str(e)}")
                continue

    except Exception as e:
        print(f"Error extracting channels: {str(e)}")

    return all_vod_links


def save_vod_links(vod_links, output_file):
    """Save VOD links to a file"""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    # Read existing links if file exists
    existing_links = set()
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            existing_links = set(line.strip() for line in f if line.strip())

    # Add new links
    new_links = set(vod_links) - existing_links

    # Write all links back to file
    with open(output_file, "w") as f:
        for link in sorted(existing_links.union(new_links)):
            f.write(f"{link}\n")

    print(
        f"Found {len(new_links)} new VOD links (total: {len(existing_links) + len(new_links)})"
    )
    return new_links


def main():
    parser = argparse.ArgumentParser(
        description="Extract Twitch VOD links from followed channels"
    )
    parser.add_argument("--username", "-u", required=True, help="Twitch username")
    parser.add_argument("--password", "-p", required=True, help="Twitch password")
    parser.add_argument(
        "--output", "-o", default="vod_links.txt", help="Output file for VOD links"
    )
    parser.add_argument(
        "--max-channels",
        type=int,
        default=50,
        help="Maximum number of channels to check",
    )
    parser.add_argument(
        "--max-vods", type=int, default=5, help="Maximum number of VODs per channel"
    )
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    args = parser.parse_args()

    # Set up Chrome options
    chrome_options = Options()
    if args.headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")

    # Initialize the browser
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    try:
        # Login to Twitch
        if login_to_twitch(driver, args.username, args.password):
            # Extract VOD links
            vod_links = extract_vods_from_following(
                driver, args.max_channels, args.max_vods
            )

            # Save links to file
            new_links = save_vod_links(vod_links, args.output)

            print(
                f"VOD link extraction complete. Found {len(vod_links)} VODs, {len(new_links)} new."
            )
        else:
            print("Failed to login to Twitch. VOD extraction aborted.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
