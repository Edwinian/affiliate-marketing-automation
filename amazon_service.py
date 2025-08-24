from dotenv import load_dotenv
from amazon_paapi import AmazonApi, models

from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import CustomLinksKey

load_dotenv()


class AmazonService(AffiliateProgram):
    CUSTOM_LINKS_KEY = CustomLinksKey.AMAZON

    def __init__(self):
        self.amazon = AmazonApi("KEY", "SECRET", "TAG", "COUNTRY")

    def get_affiliate_links(self, limit: int = 5) -> list[AffiliateLink]:
        """
        Fetch affiliate links from Amazon PA API with pagination, returning the link with the most reviews for each keyword.
        Returns an AffiliateLink dataclass with the URL, review count, and product category.
        """

        try:
            keywords = self.llm_service.generate_text(
                f"what is the best amazon affiliate product to promote nowadays? Give me {limit} keywords to search, separated by comma to be split into list of string in python, return keywords only"
            )
            keywords = keywords.split(",")
            affiliate_links = []

            # Get the best affiliate link based on the number of reviews for each keyword
            for keyword in keywords:
                response = self.amazon.search_items(
                    keywords=keyword,
                    search_index="All",
                    item_count=10,
                    item_page=1,  # Pagination parameter
                    resources=[
                        "ItemInfo.Title",
                        "Offers.Listings.Price",
                        "ItemInfo.CustomerReviews",
                        "ItemInfo.Classifications",
                    ],
                    sort_by=models.SortBy.AVGCUSTOMERREVIEWS,
                )

                if response.items:
                    # Initialize variables to track the link with the most reviews
                    best_link = None
                    max_reviews = 0

                    for item in response.items:
                        affiliate_link = item.detail_page_url

                        if not affiliate_link:
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

                    affiliate_links.append(best_link)

            return affiliate_links

        except Exception as e:
            self.logger.error(f"Error fetching affiliate link: {e}")

        # Return default AffiliateLink if no valid link is found or an error occurs
        return AffiliateLink(url="", review_count=0, categories=["Unknown"])
