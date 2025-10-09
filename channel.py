import random
from abc import ABC, abstractmethod
from typing import Optional

from all_types import AffiliateLink, CreateChannelResponse
from constants import PROMPT_SPLIT_JOINER
from enums import LlmErrorPrompt, ProgramBrand
from llm_service import LlmService
from logger_service import LoggerService
from media_service import MediaService


class Channel(ABC):
    DISCLOSURE = "Disclosure: We earn a commission at no extra cost to you if you make a purchase through links here. This helps support us in creating more content for you. Thank you for your support!"
    FORBIDDEN_KEYWORDS = [brand.value.lower() for brand in ProgramBrand]

    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.llm_service = LlmService()
        self.media_service = MediaService()

    def get_keywords(
        self,
        affiliate_link: AffiliateLink,
        limit: Optional[int] = None,
    ) -> list[str]:
        def _remove_forbidden_keywords(keywords: list[str]) -> list[str]:
            """
            Remove keywords that contain forbidden brand names as they may violate affiliate program policies
            """
            clean_keywords = []

            for word in keywords:
                if all(
                    forbidden_word.lower() not in word.lower()
                    for forbidden_word in self.FORBIDDEN_KEYWORDS
                ):
                    clean_keywords.append(word)

            return clean_keywords

        try:
            prompt_splits = [
                f"Give me a list of SEO friendly keywords about the category {affiliate_link.categories[0]} and the product title: {affiliate_link.product_title}",
                f"The keywords do not contain brand names such as {', '.join(self.FORBIDDEN_KEYWORDS)}",
                f"The keywords are SEO friendly",
                f"The keywords do not directly mention the product title: {affiliate_link.product_title}",
                f"Sort the keywords by highest relevance to the category {affiliate_link.categories[0]} and the product title: {affiliate_link.product_title}",
                f"Return the keywords only separated by commas",
            ]

            if limit:
                prompt_splits.append(f"Limit to {limit} keywords")
                
            prompt = PROMPT_SPLIT_JOINER.join(prompt_splits)
            keywords_text = self.llm_service.generate_text(prompt)
            keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
            keywords = _remove_forbidden_keywords(keywords)
            return keywords
        except Exception as e:
            self.logger.error(f"Error generating keywords from model: {e}")
            return affiliate_link.categories

    def get_title(
        self,
        affiliate_link: AffiliateLink,
        category_titles: list[str] = [],
        limit: Optional[int] = None,
    ) -> str:
        focuses = [
            f"an application of {affiliate_link.product_title}",
            f"a potential consequence of not using {affiliate_link.product_title}",
        ]
        focus_idx = random.randint(0, len(focuses) - 1)
        focus = focuses[focus_idx]

        try:
            prompt_splits = [
                f"Give me one title about {affiliate_link.categories[0]} and {focus}",
                f"The title is SEO friendly",
                f"The title does not directly mention {affiliate_link.product_title}",
                f"The title separates each word with space",
                f"The title is grammatically correct with proper preposition words",
                f"The title does not directly mention {focus}",
                f"Target audience is anyone who could use {affiliate_link.product_title}",
                f"Use acronym where appropriate (e.g. VPN instead of Virtual Private Network)",
                f"Return the title only without quotes",
            ]

            if category_titles:
                prompt_splits.append(
                    f"The title should be about a different topic from existing titles: {', '.join(category_titles)}"
                )

            if affiliate_link.keywords:
                prompt_splits.append(
                    f"Prefix the title with '{affiliate_link.keywords[0]}':"
                )

            if limit:
                prompt_splits.append(
                    f"The title should be no more than {limit} characters including spaces"
                )

            prompt = PROMPT_SPLIT_JOINER.join(prompt_splits)
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
