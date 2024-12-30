import os
import pyperclip
from time import sleep

# Import the StreetViewArchiver class from the existing script
from street_view_archiver import StreetViewArchiver

def get_active_browser_url():
    """Retrieve the active tab's URL from Brave Browser (macOS)."""
    try:
        import applescript
        script = """
        tell application "Brave Browser"
            set activeTabUrl to URL of active tab of front window
        end tell
        """
        url = applescript.AppleScript(script).run()
        return url
    except Exception as e:
        print(f"Failed to get URL from browser: {e}")
        return None

def main():
    # Configuration
    API_KEY = "AIzaSyA6ldFuBN6AcKHRYkGzXzi36_G-cWkNpDw"
    CREDENTIALS_FILE = "/Users/iaoharrowe/Projects/Street View Archival Hotkey/street-view-archival-project-0d1465596d2c.json"
    DOC_ID = "1OH2ozWBn1aGDIzC0D0WiFZTRN3hlDx6Q5It8YULoO94"

    # Initialize the StreetViewArchiver class
    archiver = StreetViewArchiver(API_KEY, CREDENTIALS_FILE, DOC_ID)

    print("Press your custom hotkey to archive the current Street View location.")

    # Attempt to retrieve and process the URL
    url = get_active_browser_url()
    if url and "google.com/maps" in url:
        try:
            print(f"\nProcessing URL: {url}")
            lat, lon = archiver.extract_coordinates(url)
            print(f"Extracted coordinates: {lat}, {lon}")

            country, state = archiver.get_location_info(lat, lon)
            print(f"Location: {state}, {country}")

            archiver.archive_location(url, lat, lon, country, state)
            print("Successfully archived location!")
        except Exception as e:
            print(f"Error: {str(e)}")
    else:
        print("No valid Google Maps URL found in the active tab.")

if __name__ == "__main__":
    main()