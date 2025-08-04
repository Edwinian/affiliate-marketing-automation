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
        self.limit = min(limit, 80)  # Ensure limit does not exceed 80

    def fetch_image_urls(self) -> List[str]:
        def fetch_page(
            url: str = "https://api.pexels.com/v1/search",
            params: Optional[dict] = None,
        ) -> None:
            try:
                # Use params only for the initial request
                response = requests.get(
                    url,
                    headers={"Authorization": os.getenv("PEXELS_API_KEY")},
                    params=params,
                )
                response.raise_for_status()  # Raise for HTTP errors (e.g., 429, 401)
                data = response.json()

                # Extract image URLs from photos
                for photo in data.get("photos", []):
                    src = photo.get("src", {})
                    url = src.get(self.size)

                    if url:
                        self.image_urls.append(url)

                # Check for next_page and recurse
                next_page = data.get("next_page")

                if next_page and len(self.image_urls) < self.limit:
                    fetch_page(url=next_page)
            except requests.RequestException as e:
                raise Exception(f"Pexels API error: {str(e)}")

        # Initial request parameters
        params = {"query": self.query, "per_page": self.limit}
        fetch_page(params=params)

    def get_image_url(self) -> Optional[str]:
        if not self.image_urls or self.used_image_count >= len(self.image_urls) - 1:
            self.image_urls = []
            self.used_image_count = 0
            self.fetch_image_urls()

        image_url = self.image_urls[self.used_image_count] if self.image_urls else None

        if image_url:
            self.used_image_count += 1
            return image_url
