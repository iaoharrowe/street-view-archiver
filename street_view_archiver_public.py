import re
import requests
import pyperclip
import time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from typing import Tuple, Optional

class StreetViewArchiver:
    def __init__(self, api_key: str, credentials_file: str, doc_id: str):
        self.api_key = api_key
        self.credentials_file = credentials_file
        self.doc_id = doc_id
        self.docs_service = None
        self._initialize_docs_service()

    def location_exists_in_doc(self, lat, lon, url):
        """Check if the given coordinates or URL already exist in the Google Doc."""
        doc_content = self.docs_service.documents().get(documentId=self.doc_id).execute()
        content = doc_content.get("body", {}).get("content", [])
        search_text = f"{lat:.6f}, {lon:.6f}"  # Search for the coordinates
        for element in content:
            if "paragraph" in element:
                text = "".join(run.get("textRun", {}).get("content", "")
                               for run in element["paragraph"]["elements"] if "textRun" in run)
                if search_text in text or url in text:
                    return True
        return False 

    def _initialize_docs_service(self):
        """Initialize the Google Docs service with credentials."""
        try:
            credentials = Credentials.from_service_account_file(self.credentials_file)
            self.docs_service = build('docs', 'v1', credentials=credentials)
        except Exception as e:
            raise Exception(f"Failed to initialize Google Docs service: {e}")

    def extract_coordinates(self, url: str) -> Tuple[float, float]:
        """Extract coordinates from Google Maps URL."""
        patterns = [
            r"@(-?\d+\.\d+),(-?\d+\.\d+)",  # @lat,lng format
            r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)"  # !3dlat!4dlng format
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                try:
                    return float(match.group(1)), float(match.group(2))
                except ValueError:
                    continue
        raise ValueError(f"Could not extract valid coordinates from URL: {url}")

    def get_location_info(self, lat: float, lon: float) -> Tuple[str, str]:
        """Get country and state information from coordinates."""
        url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={self.api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            raise ValueError(f"Geocoding API error: {data.get('status')}")

        results = data.get("results", [])
        if not results:
            raise ValueError("No results found for the given coordinates")

        country, state = None, None
        for component in results[0]["address_components"]:
            if "country" in component["types"]:
                country = component["long_name"]
            if "administrative_area_level_1" in component["types"]:
                state = component["long_name"]

        if not country or not state:
            raise ValueError("Country or state information is missing")
        return country, state

    def archive_location(self, url, lat, lon, country, state):
        """Archive the location in the Google Doc with proper formatting."""
        # Check if the location already exists
        if self.location_exists_in_doc(lat, lon, url):
            print("Location already exists in the document. Skipping...")
            return

        # Retrieve the current document content
        doc_content = self.docs_service.documents().get(documentId=self.doc_id).execute()
        content = doc_content.get("body", {}).get("content", [])

        country_index = None
        state_index = None

        # Search for existing country and state headers
        for element in content:
            if "paragraph" in element:
                text = "".join(run.get("textRun", {}).get("content", "")
                               for run in element["paragraph"]["elements"] if "textRun" in run)
                if text.strip() == country:
                    country_index = element.get("startIndex", 1)
                elif text.strip() == state:
                    state_index = element.get("startIndex", 1)

        # Prepare requests for inserting content
        requests = []

        # Insert country header if not found
        if country_index is None:
            requests.append({
                'insertText': {'location': {'index': 1}, 'text': f"{country}\n"}
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': 1, 'endIndex': len(country) + 2},
                    'paragraphStyle': {'namedStyleType': 'HEADING_1'},
                    'fields': 'namedStyleType'
                }
            })
            country_index = 1

        # Insert state header if not found
        if state_index is None:
            state_insert_index = country_index + len(country) + 1
            requests.append({
                'insertText': {'location': {'index': state_insert_index}, 'text': f"{state}\n"}
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': state_insert_index,
                        'endIndex': state_insert_index + len(state) + 1
                    },
                    'paragraphStyle': {'namedStyleType': 'HEADING_2'},
                    'fields': 'namedStyleType'
                }
            })
            state_index = state_insert_index

        # Insert hyperlinked coordinates as normal text under the state header
        coord_text = f"{lat:.6f}, {lon:.6f}\n"
        coord_index = state_index + len(state) + 1
        requests.extend([
            {
                "insertText": {
                    "location": {"index": coord_index},
                    "text": coord_text
                }
            },
            {
                "updateTextStyle": {
                    "range": {
                        "startIndex": coord_index,
                        "endIndex": coord_index + len(coord_text.strip())
                    },
                    "textStyle": {
                        "link": {"url": url}
                    },
                    "fields": "link"
                }
            },
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": coord_index,
                        "endIndex": coord_index + len(coord_text)
                    },
                    "paragraphStyle": {
                        "namedStyleType": "NORMAL_TEXT"
                    },
                    "fields": "namedStyleType"
                }
            }
        ])

        # Execute the requests to update the document
        self.docs_service.documents().batchUpdate(documentId=self.doc_id, body={'requests': requests}).execute()
        print("Data appended successfully.")

def main():
    API_KEY = "YOUR_API_KEY"
    CREDENTIALS_FILE = "CREDENTIALS_FILE"
    DOC_ID = "GOOGLE_DOC_ID"

    archiver = StreetViewArchiver(API_KEY, CREDENTIALS_FILE, DOC_ID)
    print("Waiting for a Google Maps URL to be copied to the clipboard...")

    last_url = None  # Keep track of the last URL processed
    while True:
        # Check clipboard content
        url = pyperclip.paste().strip()
        if url != last_url and "google.com/maps" in url:
            try:
                print(f"\nProcessing URL: {url}")
                lat, lon = archiver.extract_coordinates(url)
                print(f"Extracted coordinates: {lat}, {lon}")

                country, state = archiver.get_location_info(lat, lon)
                print(f"Location: {state}, {country}")

                archiver.archive_location(url, lat, lon, country, state)
                print("Successfully archived location!")
                break  # Exit after processing the first valid URL

            except Exception as e:
                print(f"Error: {str(e)}")
                break  # Exit on error
        time.sleep(0.5)  # Check the clipboard every 0.5 seconds

if __name__ == "__main__":
    main()