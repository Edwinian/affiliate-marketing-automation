import csv
from datetime import datetime, timedelta
from urllib.parse import urlencode
import uuid
import requests
from typing import Dict, List, Any, Optional

from all_types import AffiliateLink, CreateChannelResponse, Pin, UsedLink, WordpressPost
from channel import Channel
from enums import PinterestTrendType

from common import os, load_dotenv, requests


class PinterestService(Channel):
    SKIP_KEYWORDS = ["outfit ideas"]
    query_keywords_map: dict[str, list[str]] = {}

    def __init__(
        self,
        bulk_create_limit: int = 30,
        all_publish_delay_min: int = 15,
        publish_increment_min: int = 5,
    ):
        super().__init__()
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

    def get_category_counts(
        self,
        pin_sources: List[AffiliateLink | WordpressPost],
    ) -> dict[str, int]:
        count_dict = {}

        for source in pin_sources:
            for category in source.categories:  # Check every category in the list
                count_dict[
                    category
                ] += 1  # Note: This counts *any* occurrence, not just first

        return dict(count_dict)

    def get_bulk_create_from_affiliate_links_csv(
        self, affiliate_links: List[AffiliateLink], skipUsedCheck: bool = False
    ):
        unused_links = (
            affiliate_links
            if skipUsedCheck
            else self.media_service.get_unused_affiliate_links(
                affiliate_links=affiliate_links
            )
        )

        if not unused_links:
            return self.logger.info(f"No unused affiliate links.")

        csv_data = []
        all_pins = self.get_pins()
        pin_titles = [pin.title for pin in all_pins]
        pin_links = [pin.link for pin in all_pins]
        category_counts = self.get_category_counts(pin_sources=unused_links)

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
                    image_limit=category_counts[category],
                    thumbnail_url=affiliate_link.thumbnail_url,
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

        csv_file_paths = self.batch_generate_csv(csv_data)

        if csv_file_paths:
            used_links = [
                UsedLink(url=link.url) for link in affiliate_links[: len(csv_data)]
            ]
            self.media_service.add_used_affiliate_links(used_links=used_links)
            return f"CSV generation succeeded. Generated files: {', '.join(csv_file_paths)}"
        else:
            return "CSV generation failed for affiliate links."

    def generate_csv(
        self, csv_data: List[Dict[str, Any]], file_suffix: Optional[str] = None
    ) -> str:
        """
        Generates a CSV file for bulk pin creation with Pinterest-compatible headers.
        Returns the file path or empty string on failure.
        """
        if not csv_data:
            self.logger.info("No valid pin data to write to CSV.")
            return ""

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file_path = (
                f"bulk_pins_{timestamp}{f"_{file_suffix}" if file_suffix else ""}.csv"
            )
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
        image_limit: int = 1,
        thumbnail_url: Optional[str] = None,
    ):
        if len(link) > 2000:
            self.logger.warning(f"Link too long (>2000 chars), skipping: {link}")
            return

        image_url = thumbnail_url or self.media_service.get_image_url(
            query=category, limit=image_limit
        )

        if not image_url:
            self.logger.warning(f"No image found for '{title}'")
            return

        publish_date = (
            datetime.now()
            + timedelta(minutes=self.ALL_PUBLISH_DELAY_MIN + publish_delay_min)
        ).strftime("%Y-%m-%d %H:%M:%S")
        description = self.get_pin_description(title=title)

        keyword_limit = 5  # Use top 5 keywords for SEO
        keywords = (
            self.query_keywords_map.get(category, [])
            or self.get_keywords(limit=keyword_limit, include_keywords=[category])
            or self.get_keywords_from_model(
                limit=keyword_limit, include_keywords=[category]
            )
        )
        self.query_keywords_map[category] = keywords

        return {
            "Title": self.get_pin_title(title),
            "Media URL": image_url,
            "Pinterest board": category.title(),
            "Description": description,
            "Link": link,
            "Publish date": publish_date,
            "Keywords": ",".join(keywords),
        }

    def get_bulk_create_from_posts_csv(
        self, posts: List[WordpressPost], limit: Optional[int] = None
    ) -> str:
        """
        Generates a CSV for bulk creating pins from WordPress posts without pins.
        Returns the CSV file path or empty string if no pins are needed or an error occurs.
        """
        all_pins = self.get_pins()
        pin_titles = [pin.title for pin in all_pins]
        pin_links = [pin.link for pin in all_pins]
        posts_with_no_pins = [
            post
            for post in posts
            if post.link not in pin_links and post.title not in pin_titles
        ]

        if not posts_with_no_pins:
            self.logger.info("All posts already have corresponding pins.")
            return ""

        csv_data = []
        category_counts = self.get_category_counts(pin_sources=posts_with_no_pins)

        for i, post in enumerate(posts_with_no_pins):
            if len(csv_data) >= limit or self.BULK_CREATE_LIMIT:
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
                    image_limit=category_counts[category],
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

            csv_file_paths = self.batch_generate_csv(csv_data)

            if csv_file_paths:
                return f"CSV generation succeeded. Generated files: {', '.join(csv_file_paths)}"
            else:
                return "CSV generation failed for affiliate links."

    def batch_generate_csv(
        self, csv_data: list[dict[str, str]], chunk_size: int = 5
    ) -> list[str]:
        """
        Generates multiple CSV files for bulk pin creation, each containing up to chunk_size rows.
        Returns a list of file paths for the generated CSV files.
        """
        if not csv_data:
            self.logger.info("No CSV data to process.")
            return []

        csv_file_paths = []
        csv_data_chunks = [
            csv_data[i : i + chunk_size] for i in range(0, len(csv_data), chunk_size)
        ]

        for i, chunk in enumerate(csv_data_chunks):
            if chunk:
                csv_file_path = self.generate_csv(
                    csv_data=chunk, file_suffix=str(i + 1) if i > 0 else None
                )
                if csv_file_path:
                    csv_file_paths.append(csv_file_path)
                    self.logger.info(f"Generated CSV file {i+1}: {csv_file_path}")
                else:
                    self.logger.error(f"Failed to generate CSV file for chunk {i+1}")

        return csv_file_paths

    def get_keywords_from_model(
        self, limit: int = 5, include_keywords: List[str] = []
    ) -> list[str]:
        prompt = f"Generate a list of {limit} SEO friendly keywords related to {', '.join(include_keywords)} for Pinterest separated by commas. The keywords should be relevant to popular Pinterest searches and trends. Return the keywords only"

        try:
            keywords_text = self.llm_service.generate_text(prompt)
            keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
            return keywords[:limit]
        except Exception as e:
            self.logger.error(f"Error generating keywords from model: {e}")
            return include_keywords[:limit]

    def get_keywords(
        self, limit: int = 5, include_keywords: List[str] = []
    ) -> list[str]:
        """
        Retrieves the top trends from Pinterest by each trend type.
        Counts occurrences of each trend type and returns the top 'limit' trend names by count.

        Args:
            limit: Number of top trends to return
            include_keywords: Optional list of keywords to include in the trends results
        """
        trend_count: Dict[str, int] = {}

        def get_unique_keywords(
            sorted_trends: list[tuple[str, int]],
        ) -> list[tuple[str, int]]:
            """
            Process a list of keyword tuples:
            - Remove common plural endings ('s' or 'es') from each word in the keyword.
            - Filter out keywords that are substrings of other keywords, keeping longer terms.
            """
            if not sorted_trends:
                return []

            # Step 1: Remove plural endings from each keyword
            processed = []
            for keyword, count in sorted_trends:
                words = keyword.split()
                singular_words = []
                for word in words:
                    if word.endswith("es") and len(word) > 2 and word[-3] != "i":
                        singular = word[:-2]  # e.g., designs -> design
                        singular_words.append(singular)
                    elif word.endswith("s") and len(word) > 1:
                        singular = word[:-1]  # e.g., nails -> nail, outfits -> outfit
                        singular_words.append(singular)
                    else:
                        singular_words.append(word)  # e.g., hair, braid
                processed.append((" ".join(singular_words), count))

            # Step 2: Filter out keywords that are substrings of others
            unique = []
            # Sort by length (descending) and count (descending) to prioritize longer terms and higher counts
            processed = sorted(processed, key=lambda x: (-len(x[0].split()), -x[1]))
            for kw, count in processed:
                # Skip duplicates (based on keyword only)
                if any(kw == existing[0] for existing in unique):
                    continue
                # Skip if this keyword is a substring of any existing unique keyword
                if any(kw in existing[0] and kw != existing[0] for existing in unique):
                    continue
                # Remove existing unique keywords that are substrings of this one
                unique = [
                    existing
                    for existing in unique
                    if existing[0] not in kw or existing[0] == kw
                ]
                unique.append((kw, count))

            # Sort by original count (descending) and word count (descending) to match input sorting
            unique = sorted(unique, key=lambda x: (-x[1], -len(x[0].split())))
            return unique

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

        # Remove vague keywords not useful for tags
        trend_count = {
            k: v for k, v in trend_count.items() if k not in self.SKIP_KEYWORDS
        }

        # Sort trends by count (descending) and then by word count (descending) for ties
        sorted_trends = sorted(
            trend_count.items(),
            key=lambda x: (
                -x[1],
                -len(x[0].split()),
            ),
        )
        sorted_trends = get_unique_keywords(sorted_trends)

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
                f"Error refreshing token: {e} - {e.response.status_code if e.response else "No response"} {e.response.json() if e.response else str(e)}"
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

            description = self.get_pin_description(title=title)
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

    def get_pin_description(self, title: str) -> str:
        """
        Generates an SEO-friendly pin description using LlmService.
        """
        disclosure = f"\n#affiliate {self.DISCLOSURE}"
        limit = 500  # Pinterest limit
        prompt = f"Create a Pinterest description in no more than {limit - len(disclosure)} characters (including spaces) for this title that is SEO friendly, time-agnostic, suitable for affiliate marketing, and includes a call to action, respond the description only without mentioning the length limit: '{title}'"

        try:
            description = self.llm_service.generate_text(
                prompt
            ).strip()  # Remove any trailing newlines from LLM output
            description = f"{description}\n#affiliate {self.DISCLOSURE}"  # Ensure disclosure is on a new line
            return description[:limit]  # Truncate to Pinterest's 500-character limit
        except Exception as e:
            self.logger.error(f"Error generating description: {e}")
            return f"Discover the latest trends in {title.split('#')[0].strip()} to inspire your next purchase!\n#affiliate {self.DISCLOSURE}"[
                :limit
            ]


if __name__ == "__main__":
    service = PinterestService()

    # result = service.get_keywords(limit=5)
    # print(result)

    links = [
        AffiliateLink(
            categories=["fall nails"],
            url="https://amzn.to/3KnWaAs",
            product_title="KISS imPRESS Press On Nails Color FX Hidden Gem No Glue",
            thumbnail_url="https://m.media-amazon.com/images/I/71e6Fghq8KL._SL1500_.jpg",
        ),
        AffiliateLink(
            categories=["fall nails"],
            url="https://amzn.to/4gof725",
            product_title="GLAMERMAID Cherry Red Press on Nails Medium Almond, Handmade Jelly Soft Gel Dark Red Glue on Nails Stiletto, Burgundy Emo Fake Nails Short Oval, Reusable Acrylic Stick on False Nails Kit for Women",
            thumbnail_url="https://m.media-amazon.com/images/I/61xZBWKjDSL._SL1500_.jpg",
        ),
        AffiliateLink(
            categories=["fall outfits"],
            url="https://amzn.to/48dTrUb",
            product_title="Trendy Queen Women's Oversized Cable Knit Crewneck Sweaters",
            thumbnail_url="https://m.media-amazon.com/images/I/71l9N09tGUL._AC_SY741_.jpg",
        ),
        AffiliateLink(
            categories=["fall outfits"],
            url="https://amzn.to/4gmeHsW",
            product_title="Dokotoo Women's Oversized Denim Jacket Casual Long Sleeve Denim Shirts Distresse Jean Jacket Fall Outfits 2025",
            thumbnail_url="https://m.media-amazon.com/images/I/81y1FUqfhmL._AC_SY741_.jpg",
        ),
        AffiliateLink(
            categories=["winter hair braid"],
            url="https://amzn.to/41W00qB",
            product_title="K-Elewon 3 Pack Women Wide Elastic Head Wrap Headband Sports yoga Hair Band",
            thumbnail_url="https://m.media-amazon.com/images/I/71cgrDfuutL._AC_SX679_.jpg",
        ),
        AffiliateLink(
            categories=["winter hair braid"],
            url="https://amzn.to/4meIXqU",
            product_title="Acenail Wide Headbands Women Knotted Turban Headband Elastic Non Slip Hairbands Floral Workout Headbands Yoga Cotton Hair Scarfs Boho Head Wraps Fashion Hair Accessories for Women 4Pcs(Bohemian)",
            thumbnail_url="https://m.media-amazon.com/images/I/71qLcbt3qOL._SL1500_.jpg",
        ),
        AffiliateLink(
            categories=["winter fashion inspo"],
            url="https://amzn.to/4nxr1Js",
            product_title="Tickled Teal Women's Long Sleeve Casual Loose Sweater Outerwear",
            thumbnail_url="https://m.media-amazon.com/images/I/81uNGQnp5RL._AC_SX679_.jpg",
        ),
        AffiliateLink(
            categories=["winter fashion inspo"],
            url="https://amzn.to/41SNNTG",
            product_title="https://amzn.to/41SNNTG",
            thumbnail_url="https://m.media-amazon.com/images/I/71q88UCL5UL._AC_SX569_.jpg",
        ),
        AffiliateLink(
            categories=["future wedding plans"],
            url="https://amzn.to/4gozooj",
            product_title="Lillian Rose Wedding Planning Stemless Wine Glass, Height 4.75, Gold",
            thumbnail_url="https://m.media-amazon.com/images/I/61kHKXxk1UL._AC_SL1200_.jpg",
        ),
        AffiliateLink(
            categories=["future wedding plans"],
            url="https://amzn.to/3VjQnOR",
            product_title="Wedding Planning Cup - Future Mrs. 12oz Wine Tumbler with Lid and Straw - Perfect Engagement Gift For Her",
            thumbnail_url="https://m.media-amazon.com/images/I/61dqT8iUamL._AC_SL1500_.jpg",
        ),
    ]
    result = service.get_bulk_create_from_affiliate_links_csv(
        affiliate_links=links, skipUsedCheck=False
    )
    print(result)
