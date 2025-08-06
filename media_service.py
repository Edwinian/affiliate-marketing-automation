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
        self.limit = limit

    def fetch_image_urls(self):
        # Initial request parameters
        # Ensure limit does not exceed 80
        params = {"query": self.query, "per_page": min(self.limit, 80)}

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

                if url and url not in self.image_urls:
                    self.image_urls.append(url)

        except requests.RequestException as e:
            print(f"Pexels API error: {str(e)}")
            self.image_urls = []

    def get_image_url(self) -> Optional[str]:
        if self.used_image_count >= len(self.image_urls):
            self.fetch_image_urls()

        image_url = self.image_urls[self.used_image_count] if self.image_urls else None

        if image_url:
            self.used_image_count += 1
            return image_url


if __name__ == "__main__":
    service = MediaService(query="back to school outfits")
    image_url = service.get_image_url()
    print(f"Fetched image URL: {image_url}")
