from abc import ABC, abstractmethod
from typing import Optional

from all_types import AffiliateLink, CreateChannelResponse
from llm_service import LlmService
from logger_service import LoggerService
from media_service import MediaService


class Channel(ABC):
    DISCLOSURE = "Disclosure: We do not work for any company of the products or services mentioned. At no extra cost to you, we may earn a small commission from purchases made through links here. This income helps support creating more content for you. Thank you for your support!"
    KEYWORD_LIMIT = 2

    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.llm_service = LlmService()
        self.media_service = MediaService()

    def get_title(self, affiliate_link: AffiliateLink) -> str:
        try:
            prompt = f"Give me one post title about the category {affiliate_link.categories[0]} and the product title: {affiliate_link.product_title}, that is SEO friendly and time-agnostic, without directly mentioning the product, return the title only without quotes."
            return self.llm_service.generate_text(prompt)
        except Exception as e:
            self.logger.info(f"Error generating title: {e}")
            return f"{affiliate_link.categories[0]}"

    def get_keywords(self) -> list[str]:
        keywords = self.llm_service.generate_text(
            f"what are the best affiliate products to promote nowadays? Give me {self.KEYWORD_LIMIT} keywords to search for, separated by comma to be split into list of string in python, return keywords only"
        )
        keywords = keywords.split(",")
        return keywords

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
