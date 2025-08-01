import os
import requests
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class MediaService:
    def get_image_urls(
        self, query: str, size: str = "original", limit: int = 80
    ) -> List[str]:
        fetch_image_urls = []

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
                    url = src.get(size)

                    if url:
                        fetch_image_urls.append(url)

                # Check for next_page and recurse
                next_page = data.get("next_page")

                if next_page and len(fetch_image_urls) < limit:
                    fetch_page(url=next_page)
            except requests.RequestException as e:
                raise Exception(f"Pexels API error: {str(e)}")

        # Initial request parameters
        params = {"query": query, "per_page": min(limit, 80)}
        fetch_page(params=params)
        return fetch_image_urls[:limit]
