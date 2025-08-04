import requests
from typing import List
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()  # Loads the .env file


class PinterestService:
    def __init__(self):
        """Initialize PinterestService with an access token."""
        self.base_url = "https://api.pinterest.com/v5"
        self.headers = {
            "Authorization": f"Bearer {os.getenv('PINTEREST_TOKEN')}",
            "Content-Type": "application/json",
        }

    def get_trends(self) -> List[str]:
        """
        Calls Pinterest Trends API and returns a list of the top 3 latest retail trends
        from the last 6 months.
        """
        try:
            # Placeholder endpoint for trends; adjust based on actual Pinterest Trends API
            url = f"{self.base_url}/trends/keywords"
            six_months_ago = (datetime.now() - timedelta(days=180)).isoformat()
            params = {"category": "retail", "since": six_months_ago, "limit": 3}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()

            # Assuming API returns a list of trend keywords
            trends = [item["keyword"] for item in data.get("data", [])[:3]]
            return trends
        except requests.RequestException as e:
            print(f"Error fetching trends: {e}")
            return []

    def create_board(self, name: str, description: str = "") -> str:
        """
        Creates a Pinterest board with the given name and optional description.
        Returns the board ID.
        """
        try:
            url = f"{self.base_url}/boards"
            payload = {"name": name, "description": description}
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            board_id = response.json().get("id")
            return board_id
        except requests.RequestException as e:
            print(f"Error creating board: {e}")
            return ""

    def create_board_section(self, board_id: str, section_name: str) -> str:
        """
        Creates a section in the specified board with the given section name.
        Returns the section ID.
        """
        try:
            url = f"{self.base_url}/boards/{board_id}/sections"
            payload = {"name": section_name}
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            section_id = response.json().get("id")
            return section_id
        except requests.RequestException as e:
            print(f"Error creating board section: {e}")
            return ""

    def create_pin(
        self, board_id: str, image_url: str, title: str, description: str = ""
    ) -> str:
        """
        Creates a pin on the specified board with the given image URL, title, and optional description.
        Returns the pin ID.
        """
        try:
            url = f"{self.base_url}/pins"
            payload = {
                "board_id": board_id,
                "title": title,
                "description": description,
                "media_source": {"source_type": "image_url", "url": image_url},
            }
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            pin_id = response.json().get("id")
            return pin_id
        except requests.RequestException as e:
            print(f"Error creating pin: {e}")
            return ""
