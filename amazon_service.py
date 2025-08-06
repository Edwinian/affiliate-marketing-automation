import os
from typing import List, Optional
from dotenv import load_dotenv
from amazon_paapi import AmazonApi

load_dotenv()


class AmazonService:
    affiliate_links: List[str] = []
    used_link_count: int = 0

    def __init__(self, query: str, limit: int = 10):
        self.query = query
        self.limit = limit
        self.amazon = AmazonApi("KEY", "SECRET", "TAG", "COUNTRY")

    def fetch_affiliate_links(self):
        try:
            # Search for products using the query
            response = self.amazon.search_items(
                keywords=self.query,
                search_index="All",  # Broad search across all categories
                item_count=min(
                    self.limit, 10
                ),  # Amazon PA API allows max 10 items per request
            )
            self.affiliate_links = []

            if response.items:
                for item in response.items:
                    affiliate_link = item.detail_page_url

                    if (
                        item.offers
                        and item.offers.listings
                        and affiliate_link not in self.affiliate_links
                    ):
                        self.affiliate_links.append(affiliate_link)

            if not self.affiliate_links:
                print(f"No products found for query: {self.query}")
        except Exception as e:
            print(f"Error querying Amazon API for query '{self.query}': {e}")
            self.affiliate_links = []

    def get_affiliate_link(self) -> Optional[str]:
        if self.used_link_count >= len(self.affiliate_links):
            self.fetch_affiliate_links()

        affiliate_link = (
            self.affiliate_links[self.used_link_count] if self.affiliate_links else None
        )

        if affiliate_link:
            self.used_link_count += 1
            return affiliate_link


if __name__ == "__main__":
    service = AmazonService(query="Anime")
    affiliate_link = service.get_affiliate_link()
    print(f"Fetched affiliate link: {affiliate_link}")
