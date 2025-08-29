import csv
from datetime import datetime, timedelta
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
    def __init__(
        self,
        bulk_create_limit: int = 30,
        all_publish_delay_min: int = 0,
        publish_increment_min: int = 15,
    ):
        super().__init__()
        self.wordpress_service = WordpressService()
        self.base_url = "https://api.pinterest.com/v5"
        self.headers = {
            "Authorization": f"Bearer {os.getenv('PINTEREST_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
        }

        # Bulk create config
        self.BULK_CREATE_LIMIT = bulk_create_limit
        self.ALL_PUBLISH_DELAY_MIN = (
            all_publish_delay_min  # Publish all pins after X min
        )
        self.PUBLISH_INCREMENT_MIN = publish_increment_min  # Publish pin with X min apart to avoid potential spam flag from Pinterest

        # Check token validity and refresh if necessary
        if not self.is_token_valid():
            self.logger.warning("Access token is invalid, attempting to refresh.")
            if not self.refresh_access_token():
                self.logger.error("Failed to refresh access token.")

    def get_bulk_create_csv(self, affiliate_links: List[AffiliateLink] = []) -> str:
        """
        Generates a CSV for bulk creating pins from affiliate links or blog posts.
        Returns the CSV file path on success.
        """
        return (
            self.get_bulk_create_from_affiliate_links_csv(affiliate_links)
            if affiliate_links
            else self.get_bulk_create_from_posts_csv()
        )

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
        all_pins = self.get_pins()
        pin_titles = [pin.title for pin in all_pins]
        pin_links = [pin.link for pin in all_pins]

        for i, affiliate_link in enumerate(unused_links):
            if len(csv_data) >= self.BULK_CREATE_LIMIT:
                break

            try:
                title = self.get_title(affiliate_link)
                link = affiliate_link.url
                csv_titles = [row["Title"] for row in csv_data]

                if title in csv_titles:
                    self.logger.info(f"'{title}' already in CSV, skipping.")
                    continue

                if title in pin_titles or link in pin_links:
                    self.logger.info(
                        f"Affiliate link '{link}' already has a pin, skipping."
                    )
                    continue

                category = (
                    affiliate_link.categories[0]
                    if affiliate_link.categories
                    else "Others"
                )
                board_id = self._get_board_id(category)

                if not board_id:
                    self.logger.warning(f"No valid board for category '{category}'")
                    continue

                data_row = self.get_csv_row_data(
                    title=title,
                    category=category,
                    link=link,
                    publish_delay_min=i * self.PUBLISH_INCREMENT_MIN,
                )

                if not data_row:
                    continue

                self.logger.info(
                    f"Prepared csv pin data - Title: {title}, Board ID: {board_id}, Link: {link}"
                )

                csv_data.append(data_row)
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

    def generate_csv(self, csv_data: List[Dict[str, Any]]) -> str:
        """
        Generates a CSV file for bulk pin creation with Pinterest-compatible headers.
        Returns the file path or empty string on failure.
        """
        if not csv_data:
            self.logger.info("No valid pin data to write to CSV.")
            return ""

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file_path = f"bulk_pins_{timestamp}.csv"
            with open(
                csv_file_path, mode="w", newline="", encoding="utf-8"
            ) as csv_file:
                fieldnames = [
                    "Title",
                    "Media URL",
                    "Pinterest board",
                    "Description",
                    "Link",
                    "Publish date",
                    "Keywords",
                ]
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                for row in csv_data:
                    writer.writerow(row)
            self.logger.info(f"CSV file created successfully: {csv_file_path}")
            return csv_file_path
        except Exception as e:
            self.logger.error(f"Error writing CSV file: {e}")
            return ""

    def get_pin_title(self, title: str) -> str:
        title_limit = 100  # Pinterest allows up to 100 characters

        if len(title) <= title_limit:
            return title

        paraphrase_title = self.llm_service.generate_text(
            f"Paraphrase this title to be less than {title_limit} characters (including spaces) without losing its meaning: '{title}'"
        )

        return paraphrase_title[:title_limit]

    def get_csv_row_data(
        self,
        title: str,
        category: str,
        link: str,
        publish_delay_min: int,
    ):
        if len(link) > 2000:
            self.logger.warning(f"Link too long (>2000 chars), skipping: {link}")
            return

        image_urls = self.media_service.get_image_urls(query=title, limit=1)

        if not image_urls:
            self.logger.warning(f"No image found for '{title}'")
            return

        image_url = image_urls[0]
        publish_date = (
            datetime.now()
            + timedelta(minutes=self.ALL_PUBLISH_DELAY_MIN + publish_delay_min)
        ).strftime("%Y-%m-%d %H:%M:%S")
        keywords = self.get_keywords(
            limit=5, include_keywords=[category]
        )  # Use top 5 keywords for SEO
        description = self.get_pin_description(title=title, link=link)

        return {
            "Title": self.get_pin_title(title),
            "Media URL": image_url,
            "Pinterest board": category,
            "Description": description,
            "Link": link,
            "Publish date": publish_date,
            "Keywords": ",".join(keywords),
        }

    def get_bulk_create_from_posts_csv(self) -> str:
        """
        Generates a CSV for bulk creating pins from WordPress posts without pins.
        Returns the CSV file path or empty string if no pins are needed or an error occurs.
        """
        all_posts = self.wordpress_service.get_posts()
        all_pins = self.get_pins()
        pin_titles = [pin.title for pin in all_pins]
        pin_links = [pin.link for pin in all_pins]
        posts_with_no_pins = [
            post
            for post in all_posts
            if post.link not in pin_links and post.title not in pin_titles
        ]

        if not posts_with_no_pins:
            self.logger.info("All posts already have corresponding pins.")
            return ""

        csv_data = []

        for i, post in enumerate(posts_with_no_pins):
            if len(csv_data) >= self.BULK_CREATE_LIMIT:
                break

            try:
                title = post.title
                csv_titles = [row["Title"] for row in csv_data]

                if title in csv_titles:
                    self.logger.info(f"'{title}' already in CSV, skipping.")
                    continue

                category = post.categories[0].name if post.categories else "Others"
                link = post.link
                board_id = self._get_board_id(category)

                if not board_id:
                    self.logger.warning(f"No valid board for category '{category}'")
                    continue

                data_row = self.get_csv_row_data(
                    title=title,
                    category=category,
                    link=link,
                    publish_delay_min=i * self.PUBLISH_INCREMENT_MIN,
                )

                if not data_row:
                    continue

                self.logger.info(
                    f"Prepared CSV pin data - Title: {title}, Board ID: {board_id}, Link: {link}"
                )

                csv_data.append(data_row)
            except Exception as e:
                self.logger.error(f"Error processing post '{post.title}': {e}")
                continue

        return self.generate_csv(csv_data)

    def get_keywords(
        self, limit: int = 2, include_keywords: List[str] = []
    ) -> list[str]:
        """
        Retrieves the top trends from Pinterest by each trend type.
        Counts occurrences of each trend type and returns the top 'limit' trend names by count.

        Args:
            limit: Number of top trends to return
            include_keywords: Optional list of keywords to include in the trends results
        """
        trend_count: Dict[str, int] = {}

        def _get_trends(trend_type: PinterestTrendType):
            try:
                # Build the base URL
                url = f"{self.base_url}/trends/keywords/US/top/{trend_type}?limit=20"

                # Add include_keywords parameter if provided
                if include_keywords:
                    # URL encode each keyword and join with commas
                    encoded_keywords = [
                        requests.utils.quote(keyword) for keyword in include_keywords
                    ]
                    keywords_param = ",".join(encoded_keywords)
                    url += f"&include_keywords={keywords_param}"

                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                trends = data.get("trends", [])
                trend_names = [trend.get("keyword", None) for trend in trends]
                return [name for name in trend_names if name is not None]
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
        return [trend for trend, _ in sorted_trends[:limit]]

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

            description = self.get_pin_description(title=title, link=link)
            url = f"{self.base_url}/pins"
            payload = {
                "board_id": board_id,
                "title": self.get_pin_title(title),
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

    def get_pin_description(self, title: str, link: str = "") -> str:
        """
        Generates an SEO-friendly pin description using LlmService.
        """
        limit = 750  # Pinterest allows up to 800 characters, but using 750 to be safe
        disclosure = f"\n<small>{self.DISCLOSURE}</small>"
        is_affiliate_link = self.wordpress_service.frontend_url not in link

        if is_affiliate_link:
            limit -= len(disclosure)

        prompt = f"Create a Pinterest description in no more than {limit} characters (including spaces) for this title that is SEO friendly, time-agnostic, and suitable for affiliate marketing, respond the description only: '{title}'"

        try:
            description = self.llm_service.generate_text(prompt)

            if is_affiliate_link:
                description += disclosure

            return description[:limit]
        except Exception as e:
            self.logger.error(f"Error generating description: {e}")
            return f"Discover the latest trends in {title.split('#')[0].strip()} to inspire your next purchase!"


if __name__ == "__main__":
    service = PinterestService(bulk_create_limit=1)

    links = [
        # AffiliateLink(
        #     url="https://amzn.to/46d5C1d",
        #     product_title="Kasa Smart Plug HS103P4, Smart Home Wi-Fi Outlet Works with Alexa, Echo, Google Home & IFTTT, No Hub Required, Remote Control, 15 Amp, UL Certified, 4-Pack, White",
        #     categories=["Outlet Switches"],
        # ),
        # AffiliateLink(
        #     url="https://amzn.to/3JQsU56",
        #     product_title="Crest 3D Whitestrips Professional Effects – Teeth Whitening Kit, 22 Treatments (20 + 2 Bonus), Each with 1 Upper/1Lower, 44 Strips – Crest 3DWhite Teeth Whitening Strips",
        #     categories=["Strips"],
        # ),
        # AffiliateLink(
        #     url="https://amzn.to/4oSGC7O",
        #     product_title="Physician's Choice Probiotics 60 Billion CFU - 10 Strains + Organic Prebiotics - Immune, Digestive & Gut Health - Supports Occasional Constipation, Diarrhea, Gas & Bloating - for Women & Men - 30ct",
        #     categories=["Acidophilus"],
        # ),
        # AffiliateLink(
        #     url="https://amzn.to/45R2Tu7",
        #     product_title="Home-it Mop and Broom Holder Wall Mount Garden Tool Storage Tool Rack Storage & Organization for the Home Plastic Hanger for Closet Garage Organizer (5-position)",
        #     categories=["Storage Racks"],
        # ),
        AffiliateLink(
            url="https://amzn.to/4lKnRAy",
            product_title="Amazon Basics Dog and Puppy Pee Pads, 5-Layer Leak-Proof Super Absorbent, Quick-Dry Surface, Potty Training, Regular (22x22), 100 Count, Blue & White",
            categories=["Disposable Training Pads"],
        ),
    ]
    result = service.get_bulk_create_csv()
    print(result)
