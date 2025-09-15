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

    def get_affiliate_links(self) -> list[AffiliateLink]:
        """
        Fetch affiliate links from Amazon PA API with pagination, returning the link with the highest review count for each keyword.
        Returns a list of AffiliateLink dataclasses with the URL, review count, and product category.
        """
        try:
            affiliate_links = []
            used_links = self.aws_service.get_used_affiliate_links()
            item_page = 0
            max_pages = 10  # Limit to 10 pages to avoid excessive API calls

            while len(affiliate_links) < self.LINK_LIMIT and item_page < max_pages:
                item_page += 1
                self.logger.info(
                    f"Fetching Amazon items for niche '{self.niche}', page {item_page}..."
                )

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
                            "Images.Primary.Large",
                        ],
                        sort_by=models.SortBy.FEATURED,
                    )

                    if not response.items:
                        self.logger.debug(f"No items found on page {item_page}")
                        return []

                    # Sort items by customer_reviews.count (None treated as 0) in descending order
                    sorted_items = sorted(
                        response.items,
                        key=lambda item: item.customer_reviews.count or 0,
                        reverse=True,
                    )

                    # Process the top item (highest review count)
                    for item in sorted_items:
                        if len(affiliate_links) >= self.LINK_LIMIT:
                            break

                        affiliate_link_url = item.detail_page_url or ""
                        product_title = getattr(
                            item.item_info.title, "display_value", ""
                        )

                        # Skip invalid or used links
                        if (
                            not affiliate_link_url
                            or "amazon" in product_title.lower()
                            or affiliate_link_url in used_links
                        ):
                            continue

                        # Create AffiliateLink for the first valid item
                        product_category = (
                            item.item_info.classifications.product_group.display_value
                            if hasattr(item.item_info, "classifications")
                            else "Others"
                        )
                        thumbnail_url = (
                            item.images.primary.large.url
                            if hasattr(item, "images")
                            and hasattr(item.images, "primary")
                            and hasattr(item.images.primary, "large")
                            else None
                        )
                        affiliate_link = AffiliateLink(
                            url=affiliate_link_url,
                            product_title=product_title,
                            categories=[product_category],
                            thumbnail_url=thumbnail_url,
                        )
                        affiliate_links.append(affiliate_link)
                except Exception as e:
                    self.logger.error(
                        f"Error fetching items from Amazon on page {item_page}: {e}"
                    )
                    continue

            self.logger.info(
                f"Retrieved {len(affiliate_links)} affiliate links for niche '{self.niche}'"
            )
            return affiliate_links

        except Exception as e:
            self.logger.error(f"Error fetching affiliate links: {e}")
        return []  # Return empty list on failure instead of AffiliateLink
