from amazon_paapi import models, AmazonApi

from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramKey

from common import os, load_dotenv


class AmazonService(AffiliateProgram):
    def __init__(self, niche: str = "beauty"):
        self.amazon = AmazonApi(
            key=os.getenv("AMAZON_ACCESS_KEY"),
            secret=os.getenv("AMAZON_SECRET"),
            tag=os.getenv("AMAZON_ASSOCIATE_TAG"),
            country=os.getenv("AMAZON_COUNTRY"),
        )
        self.niche = niche
        self.PROGRAM_KEY = f"{ProgramKey.AMAZON}_{self.niche.upper().replace(' ', '_')}"
        super().__init__()

    def get_affiliate_links(self, limit=1) -> list[AffiliateLink]:
        """
        Fetch affiliate links from Amazon PA API with pagination, returning the link with the most reviews for each keyword.
        Returns an AffiliateLink dataclass with the URL, review count, and product category.
        """
        try:
            affiliate_links = []
            used_links = self.aws_service.get_used_affiliate_links()
            item_page = 0

            while len(affiliate_links) <= limit and item_page < 10:
                item_page += 1

                try:
                    response = self.amazon.search_items(
                        keywords=self.niche,
                        search_index="All",
                        item_count=10,
                        item_page=item_page,
                        resources=[
                            "ItemInfo.Title",
                            "Offers.Listings.Price",
                            "ItemInfo.CustomerReviews",
                            "ItemInfo.Classifications",
                            "Images.Primary.Large",  # Thumbnail URL
                        ],
                        sort_by=models.SortBy.FEATURED,
                    )

                    if response.items:
                        # Initialize variables to track the link with the most reviews
                        best_link = None
                        max_reviews = 0

                        for item in response.items:
                            affiliate_link_url = item.detail_page_url or ""
                            product_title = item.item_info.title.display_value

                            if (
                                not affiliate_link_url
                                or "amazon" in product_title.lower()
                                or affiliate_link_url in used_links
                            ):
                                continue

                            num_reviews = item.customer_reviews.count or 0

                            # Update best link if this item has more reviews
                            if num_reviews > max_reviews:
                                max_reviews = num_reviews
                                product_category = (
                                    item.item_info.classifications.product_group.display_value
                                    if item.item_info.classifications
                                    else "Others"
                                )
                                thumbnail_url = (
                                    item.images.primary.large.url
                                    if item.images
                                    and item.images.primary
                                    and item.images.primary.large
                                    else None
                                )
                                best_link = AffiliateLink(
                                    url=affiliate_link_url,
                                    product_title=product_title,
                                    categories=[product_category],
                                    thumbnail_url=thumbnail_url,
                                )

                                max_reviews = num_reviews

                        affiliate_links.append(best_link)
                except Exception as e:
                    self.logger.error(f"Error fetching items from Amazon: {e}")
                    continue

            return affiliate_links

        except Exception as e:
            self.logger.error(f"Error fetching affiliate link: {e}")

        # Return default AffiliateLink if no valid link is found or an error occurs
        return AffiliateLink(url="", categories=["Unknown"])
