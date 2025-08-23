import requests
from typing import List
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from all_types import AffiliateLink
from channel_service import ChannelService
from llm_service import LlmService

load_dotenv()  # Loads the .env file


class PinterestService(ChannelService):
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
                self.logger.info("No boards found, creating one.")
                self.create_board("Default Board", "This is a default board.")
                return self._get_board_id()

            return boards[0].get("id", "")
        except requests.RequestException as e:
            self.logger.error(f"Error fetching boards: {e}")
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
            self.logger.error(f"Error fetching trends: {e}")
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
            self.logger.error(f"Error creating board: {e}")
            return ""

    def create_board_section(self, section_name: str) -> str:
        """
        Creates a section in the first board retrieved from the user's boards.
        Returns the section ID.
        """
        try:
            board_id = self._get_board_id()
            if not board_id:
                self.logger.info("Cannot create section: No valid board ID found.")
                return ""
            url = f"{self.base_url}/boards/{board_id}/sections"
            payload = {"name": section_name}
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            section_id = response.json().get("id")
            return section_id
        except requests.RequestException as e:
            self.logger.error(f"Error creating board section: {e}")
            return ""

    def create(self, title: str, image_url: str, affiliate_link: AffiliateLink) -> str:
        """
        Creates a pin on the specified board with the given image URL, and optional affiliate link.
        Returns the pin ID.
        """
        try:
            board_id = self._get_board_id()

            if not board_id:
                self.logger.info("No valid board ID found.")
                return ""

            # Include affiliate link in description if provided
            description = self.get_pin_description(title)

            if affiliate_link:
                description += (
                    f"\nShop now: {affiliate_link.url} #affiliate\n{self.DISCLOSURE}"
                )

            url = f"{self.base_url}/pins"
            payload = {
                "board_id": board_id,
                "title": title,
                "description": description,
                "media_source": {"source_type": "image_url", "url": image_url},
                "link": (
                    affiliate_link if affiliate_link else None
                ),  # Set destination link
            }
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            pin_id = response.json().get("id")
            self.logger.info(f"Created pin {pin_id}")
            return pin_id
        except requests.RequestException as e:
            self.logger.error(
                f"Error creating pin: {e.response.status_code if e.response else 'No response'} - {e.response.json() if e.response else str(e)}"
            )
            return ""

    def get_pin_description(self, title: str) -> str:
        """
        Generates an SEO-friendly pin description using LlmService.
        """
        prompt = f"Create a Pinterest description for this title that is SEO friendly, time-agnostic, and suitable for affiliate marketing, respond the description only: '{title}'"
        try:
            response = self.llm_service.generate_text(prompt)
            return response
        except Exception as e:
            self.logger.error(f"Error generating description: {e}")
            return f"Discover the latest trends in {title.split('#')[0].strip()} to inspire your next purchase!"
