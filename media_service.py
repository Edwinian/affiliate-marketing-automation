from typing import Optional
from all_types import AffiliateLink, UsedLink
from aws_service import AWSService
from logger_service import LoggerService

from common import os, load_dotenv, requests


class MediaService:
    fetched_image_urls = []

    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.aws_service = AWSService()

    def fetch_image_urls(
        self,
        limit: int,
        size: str,
        query: Optional[str] = None,
        next_page: Optional[str] = None,
    ) -> Optional[list[str]]:
        """
        Fetch image URLs from Pexels API with pagination.
        """
        try:
            if next_page:
                response = requests.get(url=next_page)
            else:
                url = "https://api.pexels.com/v1/search"
                params = {"query": query, "per_page": 80}
                response = requests.get(
                    url,
                    headers={"Authorization": os.getenv("PEXELS_API_KEY")},
                    params=params,
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
                return self.fetch_image_urls(
                    next_page=next_page, limit=limit, size=size
                )
        except requests.RequestException as e:
            self.logger.error(f"Pexels API error for query '{query}': {str(e)}")

    def get_image_urls(
        self,
        query: str,
        limit: int = 1,
        size: str = "original",
    ) -> Optional[list[str]]:
        if len(self.fetched_image_urls) < limit:
            self.fetch_image_urls(query=query, size=size, limit=limit)

        return self.fetched_image_urls

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
