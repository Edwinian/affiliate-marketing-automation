from abc import ABC, abstractmethod
from typing import Optional

from all_types import AffiliateLink, CreateChannelResponse, WordpressPost
from enums import LlmErrorPrompt
from llm_service import LlmService
from logger_service import LoggerService
from media_service import MediaService


class Channel(ABC):
    DISCLOSURE = "Disclosure: We do not work for any company of the products or services mentioned. At no extra cost to you, we may earn a small commission from purchases made through links here. This income helps support creating more content for you. Thank you for your support!"

    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.llm_service = LlmService()
        self.media_service = MediaService()

    def get_title(
        self, affiliate_link: AffiliateLink, category_titles: list[str] = []
    ) -> str:
        try:
            prompt = f"Give me one post title about the category {affiliate_link.categories[0]} and the product title: {affiliate_link.product_title}, that is SEO friendly and time-agnostic, without directly mentioning the product, return the title only without quotes."

            if category_titles:
                prompt += f" The title relates to but should not overlap with existing titles: {', '.join(category_titles)}"

            title = self.llm_service.generate_text(prompt)

            if category_titles and LlmErrorPrompt.LENGTH_EXCEEDED in title:
                category_titles.pop()
                return self.get_title(affiliate_link, category_titles=category_titles)

            return title
        except Exception as e:
            self.logger.info(f"Error generating title: {e}")
            return f"{affiliate_link.categories[0]}"

    @abstractmethod
    def create(
        self, title: str, affiliate_link: AffiliateLink, image_url: Optional[str] = None
    ) -> CreateChannelResponse:
        """
        Creates content on the channel with the given image, trend, and optional affiliate link.

        Args:
            image_url (str): URL of the image to include in the content.
            trend (str): The retail trend for the content (e.g., "sneakers").
            affiliate_link (str, optional): Affiliate link for monetization. Defaults to empty string.

        Returns:
            str: Identifier or URL of the created content (e.g., Pin ID, post URL), or empty string on failure.
        """
        pass
