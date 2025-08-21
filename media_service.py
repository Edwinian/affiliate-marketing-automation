import os
import requests
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class MediaService:
    image_urls: List[str] = []
    used_image_count: int = 0

    def __init__(self, query: str, size: str = "original", limit: int = 80):
        self.query = query
        self.size = size
        self.limit = min(limit, 80)  # Pexels API caps per_page at 80
        self.fetch_image_urls()  # Fetch initial images during initialization

    def fetch_image_urls(self):
        """
        Fetch image URLs from Pexels API with pagination.
        """
        self.image_urls = []  # Clear existing URLs to avoid duplicates
        self.used_image_count = 0  # Reset counter
        current_count = 0
        url = "https://api.pexels.com/v1/search"
        params = {"query": self.query, "per_page": min(self.limit, 80)}

        while current_count < self.limit:
            try:
                response = requests.get(
                    url,
                    headers={"Authorization": os.getenv("PEXELS_API_KEY")},
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                # Extract image URLs
                for photo in data.get("photos", []):
                    src = photo.get("src", {})
                    image_url = src.get(self.size)
                    if image_url and image_url not in self.image_urls:
                        self.image_urls.append(image_url)
                        current_count += 1
                        if current_count >= self.limit:
                            break

                print(
                    f"fetch_image_urls count for {self.query}: ", len(self.image_urls)
                )

                # Check for next page
                next_page = data.get("next_page")
                if not next_page:
                    break
                url = next_page
                params = (
                    None  # Clear params for subsequent requests (uses next_page URL)
                )
            except requests.RequestException as e:
                print(f"Pexels API error for query '{self.query}': {str(e)}")
                break

        if not self.image_urls:
            print(f"No images found for query: {self.query}")

    def get_image_url(self) -> Optional[str]:
        """
        Return a single image URL. Fetch new images if the list is empty or exhausted.

        Returns:
            Optional[str]: A single image URL or None if none available.
        """
        if not self.image_urls or self.used_image_count >= len(self.image_urls):
            self.fetch_image_urls()

        if self.image_urls:
            image_url = self.image_urls[self.used_image_count]
            self.used_image_count += 1
            return image_url
        return None

    def add_affiliate_link(self, affiliate_link: str) -> None:
        """
        Write an affiliate link to used_links.txt file in the same directory.

        Args:
            affiliate_link (str): The affiliate link to record
        """
        try:
            file_path = os.path.join(os.path.dirname(__file__), "used_links.txt")
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(f"{affiliate_link}\n")
            print(f"Affiliate link recorded: {affiliate_link}")
        except Exception as e:
            print(f"Error writing affiliate link to file: {str(e)}")

    def check_affiliate_link(self, affiliate_link: str) -> bool:
        """
        Check if an affiliate link already exists in used_links.txt file.

        Args:
            affiliate_link (str): The affiliate link to check

        Returns:
            bool: True if the link exists in the file, False otherwise
        """
        try:
            file_path = os.path.join(os.path.dirname(__file__), "used_links.txt")

            # Check if file exists first
            if not os.path.exists(file_path):
                return False

            # Read all links from the file
            with open(file_path, "r", encoding="utf-8") as file:
                existing_links = file.read().splitlines()

            # Check if the affiliate link exists in the list (case-sensitive)
            return affiliate_link in existing_links

        except Exception as e:
            print(f"Error reading affiliate links file: {str(e)}")
            return False
