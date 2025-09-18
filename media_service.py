import random
from typing import Optional
from all_types import AffiliateLink, UsedLink
from aws_service import AWSService
from logger_service import LoggerService

from common import os, load_dotenv, requests


class MediaService:
    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.aws_service = AWSService()

    def fetch_image_urls(
        self,
        limit: int = 1,
        size: str = "original",
        query: Optional[str] = None,
        next_page: Optional[str] = None,
        fetched_image_urls: Optional[list[str]] = [],
    ) -> list[str]:
        """
        Fetch image URLs from Pexels API with pagination, preserving relevance order.

        Args:
            limit (int): Maximum number of URLs to fetch.
            size (str): Image size (e.g., 'original', 'large').
            query (Optional[str]): Search query for images.
            next_page (Optional[str]): URL for the next page of results.
            fetched_image_urls (Optional[list[str]]): Accumulated image URLs.

        Returns:
            list[str]: List of image URLs in relevance order, up to the limit.
        """
        try:
            if next_page:
                response = requests.get(url=next_page)
            else:
                url = "https://api.pexels.com/v1/search"
                params = {"query": query.lower(), "per_page": 80}
                response = requests.get(
                    url,
                    headers={"Authorization": os.getenv("PEXELS_API_KEY")},
                    params=params,
                )

            response.raise_for_status()
            data = response.json()
            photos = data.get("photos", [])
            sources = [photo.get("src") for photo in photos if photo.get("src")]
            fetched_image_urls += [src.get(size) for src in sources if src.get(size)]
            next_page = data.get("next_page")

            if next_page and len(fetched_image_urls) < limit:
                return self.fetch_image_urls(
                    limit=limit,
                    size=size,
                    query=query,
                    next_page=next_page,
                    fetched_image_urls=fetched_image_urls,
                )

            return fetched_image_urls
        except requests.RequestException as e:
            self.logger.error(f"Pexels API error for query '{query}': {str(e)}")
            return fetched_image_urls

    def get_image_urls(
        self,
        query: str,
        limit: int = 1,
        size: str = "original",
    ) -> list[str]:
        """
        Fetch a single unused image URL for the given query, prioritizing relevance.

        Args:
            query (str): Search query for images.
            limit (int): Number of images to fetch if cache is empty or insufficient.
            size (str): Image size (e.g., 'original', 'large').

        Returns:
            str: A single unused image URL, or empty string if none available.
        """
        query = query.lower()
        images = self.fetch_image_urls(query=query, size=size, limit=max(limit, 10))

        if not images:
            self.logger.warning(f"No images found for query '{query}'")
            return []

        return images

    def add_used_affiliate_links(self, used_links: list[UsedLink] = []) -> None:
        """
        Write an affiliate link to AWS S3
        """
        if not used_links:
            return

        try:
            formatted_links = [
                self.get_formatted_link(url=link.url, post_id=link.post_id)
                for link in used_links
            ]
            success = self.aws_service.add_used_affiliate_links(links=formatted_links)
            self.logger.info(
                f"Affiliate links {'recorded' if success else 'not recorded'}: {formatted_links}"
            )
        except Exception as e:
            self.logger.error(f"Error writing affiliate link to file: {str(e)}")

    def get_formatted_link(self, url: str, post_id: Optional[str] = None) -> str:
        """
        {url} - {post_id}
        """
        formatted_link = f"{url}"

        if post_id:
            formatted_link += f" - {post_id}"

        return formatted_link

    def get_unused_affiliate_links(
        self, affiliate_links: list[AffiliateLink] = []
    ) -> list[AffiliateLink]:
        """
        Check if an affiliate link already exists in AWS S3

        Args:
            affiliate_link (str): The affiliate link to check

        Returns:
            bool: True if the link exists in the file, False otherwise
        """

        unused_links = []

        if not affiliate_links:
            return unused_links

        try:
            used_links = self.aws_service.get_used_affiliate_links()

            if not used_links:
                return affiliate_links

            for link in affiliate_links:
                formatted_link = self.get_formatted_link(url=link.url)

                if not any(formatted_link in used_link for used_link in used_links):
                    unused_links.append(link)
        except Exception as e:
            self.logger.error(f"Error reading affiliate links file: {str(e)}")
            return False

        return unused_links


if __name__ == "__main__":
    service = MediaService()
    urls = service.fetch_image_urls(
        query="winter fashion inspo",
        limit=10,
    )
    print(urls[:5])
