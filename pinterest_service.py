import csv
from datetime import datetime
from urllib.parse import urlencode
import uuid
import requests
from typing import Dict, List, Any
import os
from dotenv import load_dotenv
from all_types import AffiliateLink, CreateChannelResponse, Pin
from channel import Channel
from enums import PinterestTrendType
from wordpress_service import WordpressService

load_dotenv()  # Loads the .env file


class PinterestService(Channel):
    def __init__(self, bulk_create_limit: int = 30):
        super().__init__()
        self.wordpress_service = WordpressService()
        self.base_url = "https://api.pinterest.com/v5"
        self.headers = {
            "Authorization": f"Bearer {os.getenv('PINTEREST_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
        }
        self.BULK_CREATE_LIMIT = bulk_create_limit
        # Check token validity and refresh if necessary
        if not self.is_token_valid():
            self.logger.warning("Access token is invalid, attempting to refresh.")
            if not self.refresh_access_token():
                self.logger.error("Failed to refresh access token.")

    def get_bulk_create_from_affiliate_links_csv(
        self, affiliate_links: List[AffiliateLink]
    ):
        channel_name = self.__class__.__name__
        unused_links = self.media_service.get_unused_affiliate_links(
            affiliate_links=affiliate_links, channel_name=channel_name
        )

        if not unused_links:
            return self.logger.info(f"No unused affiliate links.")

        csv_data = []

        for affiliate_link in unused_links[: self.BULK_CREATE_LIMIT]:
            try:
                title = self.get_title(affiliate_link)
                image_urls = self.media_service.get_image_urls(query=title, limit=1)
                image_url = image_urls[0] if image_urls else ""

                if not image_url:
                    self.logger.warning(f"No image found for post '{title}'")
                    continue

                link = affiliate_link.url
                category = (
                    affiliate_link.categories[0]
                    if affiliate_link.categories
                    else "Others"
                )
                board_id = self._get_board_id(category)
                description = self.get_pin_description(title)

                csv_data.append(
                    {
                        "board_id": board_id,
                        "title": title,
                        "description": description,
                        "link": link,
                        "image_url": image_url,
                    }
                )
            except Exception as e:
                self.logger.error(
                    f"Error executing cron for link {affiliate_link.url}: {e}"
                )
                continue

        success = self.generate_csv(csv_data)

        if success:
            self.media_service.add_used_affiliate_links(
                channel_name=channel_name, used_links=affiliate_links
            )

        return f"CSV generation {'succeeded' if success else 'failed'} for affiliate links."

    def generate_csv(self, csv_data: list[Dict[str, Any]]) -> bool:
        if not csv_data:
            self.logger.info("No valid pin data to write to CSV.")
            return False

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file_path = f"bulk_pins_{timestamp}.csv"
            with open(
                csv_file_path, mode="w", newline="", encoding="utf-8"
            ) as csv_file:
                fieldnames = ["board_id", "title", "description", "link", "image_url"]
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                for row in csv_data:
                    writer.writerow(row)

            self.logger.info(f"CSV file created successfully: {csv_file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error writing CSV file: {e}")
            return False

    def get_bulk_create_from_posts_csv(self):
        all_posts = self.wordpress_service.get_posts()
        all_pins = self.get_pins()
        pin_links = [pin.link for pin in all_pins]
        posts_with_no_pins = [post for post in all_posts if post.link not in pin_links]

        if not posts_with_no_pins:
            return self.logger.info("All posts already have corresponding pins.")

        csv_data = []

        for post in posts_with_no_pins[: self.BULK_CREATE_LIMIT]:
            try:
                title = post.title
                image_urls = self.media_service.get_image_urls(query=title, limit=1)
                image_url = image_urls[0] if image_urls else ""

                if not image_url:
                    self.logger.warning(f"No image found for post '{title}'")
                    continue

                link = post.link
                category = post.categories[0].name if post.categories else "Others"
                board_id = self._get_board_id(category)
                description = self.get_pin_description(title)

                csv_data.append(
                    {
                        "board_id": board_id,
                        "title": title,
                        "description": description,
                        "link": link,
                        "image_url": image_url,
                    }
                )

            except Exception as e:
                self.logger.error(f"Error processing post '{post.title}': {e}")
                continue

        success = self.generate_csv(csv_data)
        return f"CSV generation {'succeeded' if success else 'failed'} for posts without pins."

    def get_keywords(self) -> list[str]:
        """
        Retrieves the top trends from Pinterest by each trend type.
        Counts occurrences of each trend type and returns the top 'limit' trend names by count.
        """
        trend_count: Dict[str, int] = {}

        def _get_trends(trend_type: PinterestTrendType):
            try:
                url = f"{self.base_url}/trends/keywords/US/top/{trend_type}?limit=20"
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                trends = data.get("trends", [])
                trend_names = [trend.get("keyword", None) for trend in trends]
                return [name for name in trend_names if name is not None]
            except requests.RequestException as e:
                self.logger.error(f"Error fetching trends: {e}")
                return []
                trends = data.get("trends", [])
                trend_names = [trend.get("keyword", "") for trend in trends]
                return trend_names
            except requests.RequestException as e:
                self.logger.error(f"Error fetching trends: {e}")
                return []

        for trend_type in PinterestTrendType:
            trends = _get_trends(trend_type)
            for trend in trends:
                trend_count[trend] = trend_count.get(trend, 0) + 1

        # Sort trends by count (descending) and then by word count (descending) for ties
        sorted_trends = sorted(
            trend_count.items(),
            key=lambda x: (
                -x[1],
                -len(x[0].split()),
            ),
        )

        # Return the top 'limit' trend names
        return [trend for trend, _ in sorted_trends[: self.KEYWORD_LIMIT]]

    def is_token_valid(self) -> bool:
        url = "https://api.pinterest.com/v5/user_account"

        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return True
            else:
                self.logger.warning(
                    f"Token is invalid. Status code: {response.status_code}, Error: {response.json()}"
                )
                return False
        except requests.RequestException as e:
            print(f"Error checking token: {e}")
            return False

    def refresh_access_token(self) -> bool:
        """
        Refresh the Pinterest access token using the refresh token.
        Updates self.headers with the new access token if successful.
        """
        url = f"{self.base_url}/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": os.getenv("PINTEREST_REFRESH_TOKEN"),
            "client_id": os.getenv("PINTEREST_APP_ID"),
            "client_secret": os.getenv("PINTEREST_APP_SECRET"),
        }

        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            response_data = response.json()
            new_access_token = response_data.get("access_token")
            new_refresh_token = response_data.get(
                "refresh_token"
            )  # Optional: new refresh token if provided

            if new_access_token:
                # Update headers with new access token
                self.headers["Authorization"] = f"Bearer {new_access_token}"
                self.logger.warning("Access token refreshed successfully.")
            else:
                self.logger.error(
                    "No access token in refresh response: %s", response_data
                )
                return False

            if new_refresh_token:
                self.logger.warning("Refresh token updated.")

            return True
        except requests.RequestException as e:
            self.logger.error(
                "Error refreshing token: %s - %s",
                e.response.status_code if e.response else "No response",
                e.response.json() if e.response else str(e),
            )
            return False

    def get_pinterest_auth_url(self) -> str:
        """
        Generate Pinterest OAuth authorization URL with a unique state parameter.
        Returns the URL and the state value for verification.
        """
        redirect_uri = "http://localhost:8000/pinterest/callback"
        scopes = [
            "boards:read",
            "boards:write",
            "pins:read",
            "pins:write",
            "user_accounts:read",
            "user_accounts:write",
        ]
        state = str(uuid.uuid4())  # Unique state for CSRF protection
        base_url = "https://www.pinterest.com/oauth/"
        params = {
            "client_id": os.getenv("PINTEREST_APP_ID"),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": ",".join(scopes),
            "state": state,
        }
        return f"{base_url}?{urlencode(params)}", state

    def _get_board_id(self, name: str) -> str:
        try:
            url = f"{self.base_url}/boards"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            boards = data.get("items", [])
            board = next(
                (board for board in boards if board["name"].lower() == name.lower()),
                None,
            )

            if not board:
                self.logger.info(f"No board found for the name '{name}', creating one.")
                return self.create_board(name)

            return board["id"]
        except requests.RequestException as e:
            self.logger.error(f"Error fetching boards: {e}")
            return ""

    def get_pins(self) -> list[Pin]:
        """
        Calls Pinterest API and returns a list of the top 3 latest pins.
        """
        try:
            url = f"{self.base_url}/pins"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            pins = data.get("items", [])
            return [
                Pin(
                    id=pin.get("id", ""),
                    board_id=pin.get("board_id", ""),
                    title=pin.get("title", ""),
                    link=pin.get("link", ""),
                    description=pin.get("description", ""),
                )
                for pin in pins
            ]
        except requests.RequestException as e:
            self.logger.error(f"Error fetching pins: {e}")
            return []

    def create_board(self, name: str) -> str:
        """
        Creates a Pinterest board with the given name and optional description.
        Returns the board ID.
        """
        try:
            url = f"{self.base_url}/boards"
            description = self.llm_service.generate_text(
                f"Create a Pinterest board description based on '{name}' that is SEO friendly, time-agnostic, and suitable for affiliate marketing, return the description only"
            )
            payload = {"name": name, "description": description}
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json().get("id", "")
        except requests.RequestException as e:
            self.logger.error(f"Error creating board: {e}")
            return ""

    def create_board_section(self, board_name: str, section_name: str) -> str:
        """
        Creates a section in the board retrieved from the user's boards.
        Returns the section ID.
        """
        try:
            board_id = self._get_board_id(board_name)

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

    def create(
        self,
        title: str,
        image_url: str,
        category: str,
        link: str,
    ) -> CreateChannelResponse:
        """
        Creates a pin on the specified board with the given image URL, and optional affiliate link.
        Returns the pin ID.
        """
        try:
            board_id = self._get_board_id(category)

            if not board_id:
                self.logger.info("No valid board ID found.")
                return ""

            description = self.get_pin_description(title)
            url = f"{self.base_url}/pins"
            payload = {
                "board_id": board_id,
                "title": title,
                "description": description,
                "media_source": {"source_type": "image_url", "url": image_url},
                "link": link,
            }
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            id = data.get("id")
            self.logger.info(f"Created pin {id}")

            return CreateChannelResponse(id=id)
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
            description = self.llm_service.generate_text(prompt)
            description += f"\n<small>{self.DISCLOSURE}</small>"
            return description
        except Exception as e:
            self.logger.error(f"Error generating description: {e}")
            return f"Discover the latest trends in {title.split('#')[0].strip()} to inspire your next purchase!"


if __name__ == "__main__":
    service = PinterestService()
    result = service.get_pins()
    print(result)
