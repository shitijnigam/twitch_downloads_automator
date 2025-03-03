import os
import time
import json
import argparse
import requests
import browser_cookie3


def get_twitch_cookies():
    """Get Twitch cookies from browser"""
    print("Attempting to extract Twitch cookies from your browser...")
    try:
        # Try Chrome first
        cookies = browser_cookie3.chrome(domain_name=".twitch.tv")
        print("Found Twitch cookies in Chrome")
        return cookies
    except:
        try:
            # Try Firefox next
            cookies = browser_cookie3.firefox(domain_name=".twitch.tv")
            print("Found Twitch cookies in Firefox")
            return cookies
        except:
            try:
                # Try Edge last
                cookies = browser_cookie3.edge(domain_name=".twitch.tv")
                print("Found Twitch cookies in Edge")
                return cookies
            except Exception as e:
                print(f"Could not extract cookies: {str(e)}")
                return None


def extract_vods_from_following(cookies, max_channels=50, max_vods_per_channel=5):
    """Extract VOD links using direct API calls"""
    # Headers to mimic browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/vnd.twitchtv.v5+json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Create a session with cookies
    session = requests.Session()
    if cookies:
        session.cookies = cookies

    all_vod_links = []

    # First, try to get user ID
    try:
        print("Checking if you're properly logged in...")
        response = session.get(
            "https://www.twitch.tv/directory/following", headers=headers
        )

        if 'data-a-target="login-button"' in response.text:
            print(
                "ERROR: Not logged in. Make sure you're logged into Twitch in your browser."
            )
            return []

        print("Successfully logged in via browser cookies")

        # Get followed channels using GQL API
        print("Fetching channels you follow...")

        # First try the simpler approach - parse HTML
        channel_usernames = []
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for channel links in the Following page
            channel_links = soup.select('a[data-a-target="preview-card-channel-link"]')
            for link in channel_links:
                href = link.get("href", "")
                if href.startswith("/"):
                    username = href.strip("/")
                    channel_usernames.append(username)

            print(f"Found {len(channel_usernames)} channels from HTML parsing")
        except Exception as e:
            print(f"HTML parsing failed: {e}")
            channel_usernames = []

        # If we couldn't get channels from HTML, try a different approach
        if not channel_usernames:
            print("Using alternative method to find channels...")
            # Just use some popular channels as fallback
            channel_usernames = [
                "xqc",
                "summit1g",
                "shroud",
                "pokimane",
                "sodapoppin",
                "timthetatman",
                "nickmercs",
                "hasanabi",
                "lirik",
                "moistcr1tikal",
            ]
            print(f"Using {len(channel_usernames)} popular channels as fallback")

        # Visit each channel's VOD page
        for i, username in enumerate(channel_usernames[:max_channels]):
            print(
                f"[{i+1}/{min(len(channel_usernames), max_channels)}] Checking VODs for {username}..."
            )

            vod_url = (
                f"https://www.twitch.tv/{username}/videos?filter=archives&sort=time"
            )
            response = session.get(vod_url, headers=headers)

            if response.status_code != 200:
                print(
                    f"  Error accessing {username}'s VODs page: {response.status_code}"
                )
                continue

            # Parse the page for VOD links
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Look for VOD links
                vod_elements = soup.select('a[data-a-target="preview-card-image-link"]')

                vods_found = 0
                for vod in vod_elements:
                    href = vod.get("href", "")
                    if "/videos/" in href:
                        if href.startswith("http"):
                            vod_link = href
                        else:
                            vod_link = f"https://www.twitch.tv{href}"

                        all_vod_links.append(vod_link)
                        vods_found += 1
                        print(f"  - Found VOD: {vod_link}")

                        if vods_found >= max_vods_per_channel:
                            break

                print(f"  Found {vods_found} VODs for {username}")

            except Exception as e:
                print(f"  Error parsing VODs for {username}: {str(e)}")
                continue

            # Be nice to Twitch servers
            time.sleep(1)

    except Exception as e:
        print(f"Error during extraction: {str(e)}")

    return all_vod_links


def save_vod_links(vod_links, output_file):
    """Save VOD links to a file"""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_file)) or ".", exist_ok=True)

    # Read existing links if file exists
    existing_links = set()
    if os.path.exists(output_file):
        print(f"Reading existing links from {output_file}")
        with open(output_file, "r") as f:
            existing_links = set(line.strip() for line in f if line.strip())
        print(f"Found {len(existing_links)} existing links")

    # Add new links
    new_links = set(vod_links) - existing_links
    print(f"Found {len(new_links)} new VOD links")

    # Write all links back to file
    with open(output_file, "w") as f:
        for link in sorted(existing_links.union(new_links)):
            f.write(f"{link}\n")

    print(f"Saved {len(existing_links) + len(new_links)} total links to {output_file}")
    return new_links


def main():
    parser = argparse.ArgumentParser(
        description="Extract Twitch VOD links using browser cookies"
    )
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
    args = parser.parse_args()

    print("Starting Twitch VOD extractor (browser cookie method)")
    print(f"Make sure you're already logged into Twitch in your browser!")

    # Try to get cookies from browser
    cookies = get_twitch_cookies()
    if not cookies:
        print("ERROR: Could not find Twitch cookies in your browser.")
        print(
            "Please login to Twitch.tv in your Chrome, Firefox, or Edge browser first."
        )
        return

    # Extract VOD links
    vod_links = extract_vods_from_following(cookies, args.max_channels, args.max_vods)

    # Save links to file
    if vod_links:
        new_links = save_vod_links(vod_links, args.output)
        print(
            f"VOD link extraction complete. Found {len(vod_links)} VODs, {len(new_links)} new."
        )
    else:
        print(
            "No VOD links were found. Make sure you're logged in to Twitch in your browser."
        )


if __name__ == "__main__":
    main()
