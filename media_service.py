import os
from typing import Optional
import requests
from dotenv import load_dotenv

from all_types import AffiliateLink
from aws_service import AWSService
from logger_service import LoggerService

load_dotenv()


class MediaService:
    fetched_image_urls = []

    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.aws_service = AWSService()

    def fetch_image_urls(
        self,
        limit: int,
        query: Optional[str] = None,
        size="original",
        next_page: Optional[str] = None,
    ) -> Optional[list[str]]:
        """
        Fetch image URLs from Pexels API with pagination.
        """
        per_page_limit = 80
        limit = limit or per_page_limit
        url = "https://api.pexels.com/v1/search"
        params = {"query": query, "per_page": per_page_limit}

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
            self.logger.error(f"Pexels API error for query '{query}': {str(e)}")

    def get_image_urls(
        self,
        limit: int,
        query: Optional[str] = None,
        size="original",
    ) -> Optional[list[str]]:
        if len(self.fetched_image_urls) < limit:
            self.fetch_image_urls(query=query, size=size, limit=limit)

        used_count = min(limit, len(self.fetched_image_urls))
        image_urls = self.fetched_image_urls[:used_count]
        self.fetched_image_urls = self.fetched_image_urls[used_count:]
        return image_urls

    def add_affiliate_links(self, channel_name: str, urls: list[str] = []) -> None:
        """
        Write an affiliate link to AWS S3
        """
        if not urls:
            return

        try:
            formatted_links = [
                self.get_formatted_link(url, channel_name) for url in urls
            ]
            success = self.aws_service.add_used_affiliate_links(links=formatted_links)
            self.logger.info(f"Affiliate links recorded {success}: {urls}")
        except Exception as e:
            self.logger.error(f"Error writing affiliate link to file: {str(e)}")

    def get_formatted_link(self, url: str, channel_name: str) -> str:
        return f"{url} - {channel_name}"

    def get_unused_affiliate_links(
        self, affiliate_links: list[AffiliateLink] = [], channel_name: str = ""
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
                formatted_link = self.get_formatted_link(
                    url=link.url, channel_name=channel_name
                )

                if formatted_link not in used_links:
                    unused_links.append(link)
        except Exception as e:
            self.logger.error(f"Error reading affiliate links file: {str(e)}")
            return False

        return unused_links
