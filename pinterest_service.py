import requests
from typing import List
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from llm_service import LlmService

load_dotenv()  # Loads the .env file


class PinterestService:
    def __init__(self):
        self.base_url = "https://api.pinterest.com/v5"
        self.headers = {
            "Authorization": f"Bearer {os.getenv('PINTEREST_TOKEN')}",
            "Content-Type": "application/json",
        }
        self.llm_service = LlmService()

    def _get_board_id(self) -> str:
        try:
            url = f"{self.base_url}/boards"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            boards = data.get("items", [])

            if not boards:
                print("No boards found, creating one.")
                self.create_board("Default Board", "This is a default board.")
                return self._get_board_id()

            return boards[0].get("id", "")
        except requests.RequestException as e:
            print(f"Error fetching boards: {e}")
            return ""

    def get_trends(self) -> List[str]:
        """
        Calls Pinterest Trends API and returns a list of the top 3 latest retail trends
        from the last 6 months.
        """
        try:
            url = f"{self.base_url}/trends/keywords"
            six_months_ago = (datetime.now() - timedelta(days=180)).isoformat()
            params = {"category": "retail", "since": six_months_ago, "limit": 3}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
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
            return response.json().get("id", "")
        except requests.RequestException as e:
            print(f"Error creating board: {e}")
            return ""

    def create_board_section(self, section_name: str) -> str:
        """
        Creates a section in the first board retrieved from the user's boards.
        Returns the section ID.
        """
        try:
            # Get the first board's ID
            board_id = self._get_board_id()

            if not board_id:
                print("Cannot create section: No valid board ID found.")
                return ""

            # Create the board section
            url = f"{self.base_url}/boards/{board_id}/sections"
            payload = {"name": section_name}
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            section_id = response.json().get("id")
            return section_id
        except requests.RequestException as e:
            print(f"Error creating board section: {e}")
            return ""

    def create_pin(self, image_url: str, trend: str) -> str:
        """
        Creates a pin on the specified board with the given image URL, title, and optional description.
        Returns the pin ID.
        """
        try:
            board_id = self._get_board_id()
            title = self.get_pin_title(trend)
            description = self.get_pin_description(title)
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

    def get_pin_title(self, trend: str) -> str:
        prompt = f"Create a pinterest title about '{trend}' ideas that is SEO friendly and time-agnostic, respond the title only."
        response = self.llm_service.generate_text(prompt)
        return response

    def get_pin_description(self, title: str) -> str:
        prompt = f"Create a pinterest description for this title that is SEO friendly and time-agnostic, respond the description only: '{title}'"
        response = self.llm_service.generate_text(prompt)
        return response
