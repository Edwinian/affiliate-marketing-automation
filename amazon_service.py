import os
from typing import List, Optional
from dotenv import load_dotenv
from amazon_paapi import AmazonApi
import requests

from affiliate_program_service import AffiliateProgramService
from media_service import MediaService

load_dotenv()


class AmazonService(AffiliateProgramService):
    affiliate_links: List[str] = []
    used_link_count: int = 0

    def __init__(self, query: str, limit: int = 10):
        self.media_service = MediaService()
        self.query = query
        self.limit = limit
        self.amazon = AmazonApi("KEY", "SECRET", "TAG", "COUNTRY")

    def fetch_affiliate_links(self):
        """
        Fetch affiliate links from Amazon PA API with pagination.
        """
        self.affiliate_links = []  # Clear existing links
        self.used_link_count = 0  # Reset counter
        current_count = 0
        item_page = 1  # Start with page 1

        while current_count < self.limit:
            try:
                response = self.amazon.search_items(
                    keywords=self.query,
                    search_index="All",
                    item_count=1,
                    item_page=item_page,  # Pagination parameter
                    resources=["ItemInfo.Title", "Offers.Listings.Price"],
                )

                if response.items:
                    for item in response.items:
                        if (
                            item.detail_page_url
                            and item.detail_page_url not in self.affiliate_links
                        ):
                            self.affiliate_links.append(item.detail_page_url)
                            current_count += 1
                            if current_count >= self.limit:
                                break

                # Check for next page (NextToken)
                next_page = getattr(response.search_result, "next_token", None)
                if not next_page or item_page >= 10:  # Amazon limits to 10 pages
                    break
                item_page += 1
            except requests.RequestException as e:
                print(f"Amazon API error for query '{self.query}': {str(e)}")
                break
            except Exception as e:
                print(f"Error querying Amazon API for query '{self.query}': {e}")
                break

        if not self.affiliate_links:
            print(f"No products found for query: {self.query}")

    def get_affiliate_link(self) -> Optional[str]:
        if not self.affiliate_links or self.used_link_count >= len(
            self.affiliate_links
        ):
            self.fetch_affiliate_links()

        if self.affiliate_links:
            affiliate_link = self.affiliate_links[self.used_link_count]
            self.used_link_count += 1
            return affiliate_link
        return None

    def execute_cron(self) -> None:
        return
