import os
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()


class MediaService:
    fetched_image_urls = []

    def fetch_image_urls(
        self,
        query: Optional[str] = None,
        size="original",
        limit: int = 80,
        next_page: Optional[str] = None,
    ) -> Optional[list[str]]:
        """
        Fetch image URLs from Pexels API with pagination.
        """
        url = "https://api.pexels.com/v1/search"
        params = {"query": query, "per_page": 80}

        try:
            response = (
                requests.get(url=next_page)
                if next_page
                else requests.get(
                    url,
                    headers={"Authorization": os.getenv("PEXELS_API_KEY")},
                    params=params,
                )
            )
            response.raise_for_status()
            data = response.json()

            # Extract image URLs
            for photo in data.get("photos", []):
                if len(self.fetched_image_urls) >= limit:
                    return

                src = photo.get("src", {})
                image_url = src.get(size)

                if image_url:
                    self.fetched_image_urls.append(image_url)

            # Check for next page
            next_page = data.get("next_page")

            if next_page and len(self.fetched_image_urls) < limit:
                return self.fetch_image_urls(next_page=next_page)
        except requests.RequestException as e:
            print(f"Pexels API error for query '{query}': {str(e)}")

    def get_image_urls(
        self,
        query: Optional[str] = None,
        size="original",
        limit: int = 80,
    ) -> Optional[list[str]]:
        if len(self.fetched_image_urls) < limit:
            self.fetch_image_urls(query=query, size=size, limit=limit)

        used_count = min(limit, len(self.fetched_image_urls))
        image_urls = self.fetched_image_urls[:used_count]
        self.fetched_image_urls = self.fetched_image_urls[used_count:]
        return image_urls

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

    def is_affiliate_link_used(self, affiliate_link: Optional[str] = None) -> bool:
        """
        Check if an affiliate link already exists in used_links.txt file.

        Args:
            affiliate_link (str): The affiliate link to check

        Returns:
            bool: True if the link exists in the file, False otherwise
        """

        if not affiliate_link:
            return False

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
