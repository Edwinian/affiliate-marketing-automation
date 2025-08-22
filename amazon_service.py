from typing import Optional
from dotenv import load_dotenv
from amazon_paapi import AmazonApi

from affiliate_program_service import AffiliateProgramService
from all_types import AffiliateLink
from enums import CustomLinksKey
from llm_service import LlmService
from media_service import MediaService

load_dotenv()


class AmazonService(AffiliateProgramService):
    CUSTOM_LINKS_KEY = CustomLinksKey.AMAZON

    def __init__(self):
        self.llm_service = LlmService()
        self.media_service = MediaService()
        self.amazon = AmazonApi("KEY", "SECRET", "TAG", "COUNTRY")

    def execute_cron(self, custom_links: Optional[list[AffiliateLink]] = []) -> None:
        affiliate_links = custom_links or [self.get_affiliate_link()]

    def get_affiliate_link(self) -> AffiliateLink:
        """
        Fetch affiliate links from Amazon PA API with pagination, returning the link with the most reviews.
        Returns an AffiliateLink dataclass with the URL, review count, and product category.
        """

        try:
            keywords = self.llm_service.generate_text(
                f"what is the best amazon affiliate product to promote nowadays? Give me keywords to search and return keywords only."
            )
            response = self.amazon.search_items(
                keywords=keywords,
                search_index="All",
                item_count=10,
                item_page=1,  # Pagination parameter
                resources=[
                    "ItemInfo.Title",
                    "Offers.Listings.Price",
                    "ItemInfo.CustomerReviews",
                    "ItemInfo.Classifications",
                ],
            )

            if response.items:
                # Initialize variables to track the link with the most reviews
                best_link = None
                max_reviews = 0

                for item in response.items:
                    affiliate_link = item.detail_page_url

                    if not affiliate_link or self.media_service.is_affiliate_link_used(
                        affiliate_link
                    ):
                        continue

                    num_reviews = item.customer_reviews.count or 0
                    product_category = (
                        item.item_info.classifications.product_group.display_value
                        if item.item_info.classifications
                        else "Unknown"
                    )

                    # Update best link if this item has more reviews
                    if num_reviews > max_reviews:
                        max_reviews = num_reviews
                        best_link = AffiliateLink(
                            url=affiliate_link,
                            review_count=num_reviews,
                            categories=[product_category],
                        )

                if best_link:
                    self.media_service.add_affiliate_link(best_link.url)
                    return best_link

        except Exception as e:
            print(f"Error fetching affiliate link: {e}")

        # Return default AffiliateLink if no valid link is found or an error occurs
        return AffiliateLink(url="", review_count=0, categories=["Unknown"])
