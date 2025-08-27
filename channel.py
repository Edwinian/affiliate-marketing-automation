from abc import ABC, abstractmethod
from ast import List
from typing import Optional

from all_types import AffiliateLink
from llm_service import LlmService
from logger_service import LoggerService


class Channel(ABC):
    DISCLOSURE = "Disclosure: We do not work for any company of the products or services mentioned. At no extra cost to you, we may earn a small commission from purchases made through links here. This income helps support creating more content for you. Thank you for your support!"
    KEYWORD_LIMIT = 2

    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.llm_service = LlmService()

    def get_keywords_from_model(self) -> list[str]:
        keywords = self.llm_service.generate_text(
            f"what are the best affiliate products to promote nowadays? Give me {self.KEYWORD_LIMIT} keywords to search for, separated by comma to be split into list of string in python, return keywords only"
        )
        keywords = keywords.split(",")
        return keywords

    @abstractmethod
    def get_keywords() -> List[str]:
        """
        Abstract method to be implemented by subclasses for getting keywords.
        """
        pass

    @abstractmethod
    def create(
        self, title: str, affiliate_link: AffiliateLink, image_url: Optional[str] = None
    ) -> str:
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
