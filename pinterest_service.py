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
    SKIP_KEYWORDS = ["outfit ideas", "hair styles"]
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
            for category in source.categories:
                if category not in count_dict:
                    count_dict[category] = 0
                count_dict[category] += 1

        return count_dict

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

        def _get_unique_keywords(
            sorted_trends: list[tuple[str, int]],
        ) -> list[tuple[str, int]]:
            """
            Process a list of keyword tuples:
            - Filter out keywords that, after removing plural endings ('s' or 'es'), are substrings of other keywords.
            - Keep original keywords in the output, prioritizing longer terms and higher counts.
            """
            if not sorted_trends:
                return []

            # Helper function to get singular form for substring comparison
            def to_singular(keyword: str) -> str:
                words = keyword.split()
                singular_words = []
                for word in words:
                    if word.endswith("es") and len(word) > 2 and word[-3] != "i":
                        singular = word[:-2]  # e.g., designs -> design
                        singular_words.append(singular)
                    elif word.endswith("s") and len(word) > 1:
                        singular = word[:-1]  # e.g., nails -> nail, outfits -> outfit
                        singular_words.append(
                            word
                        )  # Keep original for non-plural cases
                    else:
                        singular_words.append(word)  # e.g., hair, braid
                return " ".join(singular_words)

            # Step 1: Create a list with original keywords and their singular forms for comparison
            processed = [
                (keyword, count, to_singular(keyword))
                for keyword, count in sorted_trends
            ]

            # Step 2: Filter out keywords whose singular form is a substring of another keyword's singular form
            unique = []
            # Sort by length of original keyword (descending) and count (descending)
            processed = sorted(processed, key=lambda x: (-len(x[0].split()), -x[1]))

            for orig_kw, count, singular_kw in processed:
                # Skip duplicates (based on original keyword)
                if any(orig_kw == existing[0] for existing in unique):
                    continue
                # Skip if this keyword's singular form is a substring of any existing unique keyword's singular form
                if any(
                    singular_kw in to_singular(existing[0])
                    and singular_kw != to_singular(existing[0])
                    for existing in unique
                ):
                    continue

                # Remove existing unique keywords whose singular form is a substring of this one
                unique = [
                    existing
                    for existing in unique
                    if to_singular(existing[0]) not in singular_kw
                    or to_singular(existing[0]) == singular_kw
                ]
                unique.append((orig_kw, count))

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
        sorted_trends = _get_unique_keywords(sorted_trends)

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
            url="https://amzn.to/4n2x2O9",
            product_title="Glamnetic Reusable Press On Nails Berry Maroon Stick On",
            thumbnail_url="https://m.media-amazon.com/images/I/61EDmFSjsfL._SL1500_.jpg",
        ),
        AffiliateLink(
            categories=["fall nails"],
            url="https://amzn.to/3IeeBqQ",
            product_title="30Pcs 3D Fall Press on Nails Medium Almond Maple Leaf Fake Nails Handmade Acrylic Nails Autumn Flower Rhinestones Glue on Nail French Tip False Nails Thanksgiving Gold Leaves Artificial Nail Decor",
            thumbnail_url="https://m.media-amazon.com/images/I/710QetAc4YL._SL1500_.jpg",
        ),
        AffiliateLink(
            categories=["fall outfits"],
            url="https://amzn.to/47G0zbR",
            product_title="Trendy Queen Women's 2 Piece Matching Lounge Set Long Sleeve Slightly Crop Top Wide Leg Pants Casual Sweatsuit",
            thumbnail_url="https://m.media-amazon.com/images/I/61icMXLgUGL._AC_SY741_.jpg",
        ),
        AffiliateLink(
            categories=["fall outfits"],
            url="https://amzn.to/4mjcujs",
            product_title="Trendy Queen Cropped Cardigan Sweaters for Women Lightweight Crop Cotton Knit Y2k Fall Outfits Fashion Clothes 2025",
            thumbnail_url="https://m.media-amazon.com/images/I/71EMLE2FjpL._AC_SY741_.jpg",
        ),
        AffiliateLink(
            categories=["winter hair braid"],
            url="https://amzn.to/3JXYqP3",
            product_title="2Pcs Braided Ponytail Extensions with Hair Ties Soft Synthetic Hair Pieces Straight Wrap Around Hair Extensions Pony Tail Hairpieces Accessories for Women Daily Wear 16 Inch (Light Brown)",
            thumbnail_url="https://m.media-amazon.com/images/I/71wt8qdskDL._SL1500_.jpg",
        ),
        AffiliateLink(
            categories=["winter hair braid"],
            url="https://amzn.to/4moglMf",
            product_title="DIGUAN 5 Strands Synthetic Hair Braided Headband Classic Chunky Wide Plaited Braids Elastic Stretch Hairpiece Women Girl Beauty accessory, 56g (#Medium Brown)",
            thumbnail_url="https://m.media-amazon.com/images/I/51nBQRyv34L._SL1001_.jpg",
        ),
        AffiliateLink(
            categories=["winter fashion inspo"],
            url="https://amzn.to/4nBZ2bB",
            product_title="Lacavocor Women's Warm Shawl Wrap Cape Winter Cardigan Sweaters Open Front Poncho",
            thumbnail_url="https://m.media-amazon.com/images/I/81Y0gBLjOhL._AC_SY741_.jpg",
        ),
        AffiliateLink(
            categories=["winter fashion inspo"],
            url="https://amzn.to/4nD537T",
            product_title="Hooever Women's Winter Wool Coat Casual Notch Lapel Single-Breasted Peacoat",
            thumbnail_url="https://m.media-amazon.com/images/I/71q88UCL5UL._AC_SX569_.jpg",
        ),
        AffiliateLink(
            categories=["future wedding plans"],
            url="https://amzn.to/4n8E5oP",
            product_title="And Per Se Wedding Planner Book and Organizer - Wedding Planning for Bride, Engagement Gifts for Couples, Future Brides and Grooms(Mystic Grey)",
            thumbnail_url="https://m.media-amazon.com/images/I/71HimmaC5lL._AC_SL1500_.jpg",
        ),
        AffiliateLink(
            categories=["future wedding plans"],
            url="https://amzn.to/48iuTcI",
            product_title="Wedding Planner Book and Organizer, Unique Engagement Gift for Newly Engaged Couples, Bride Gifts Wedding Planner Book",
            thumbnail_url="https://m.media-amazon.com/images/I/81KJ19SkCOL._AC_SL1500_.jpg",
        ),
    ]
    result = service.get_bulk_create_from_affiliate_links_csv(
        affiliate_links=links, skipUsedCheck=False
    )
    print(result)
