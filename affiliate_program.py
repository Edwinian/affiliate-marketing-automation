from abc import ABC, abstractmethod
from typing import List

from all_types import AffiliateLink
from channel import Channel
from enums import CustomLinksKey
from llm_service import LlmService
from logger_service import LoggerService
from media_service import MediaService
from pinterest_service import PinterestService
from wordpress_service import WordpressService


class AffiliateProgram(ABC):
    """
    Base class for affiliate program services that need to execute cron jobs.
    """

    CUSTOM_LINKS_KEY = CustomLinksKey.DEFAULT
    CHANNELS: list[Channel] = [
        WordpressService(),
        # PinterestService(),
    ]

    def __init__(self):
        self.program_name = self.__class__.__name__
        log_name = self.program_name
        self.logger = LoggerService(name=log_name)
        self.llm_service = LlmService()
        self.media_service = MediaService()
        self.pinterest_service = PinterestService()
        self.keywords_map = {
            "PinterestService": self.pinterest_service.get_top_trends(top_k=3),
        }

    @abstractmethod
    def get_affiliate_links(self, keywords: List[str]) -> list[AffiliateLink]:
        """
        Abstract method to be implemented by subclasses for getting affiliate link.
        """
        pass

    def get_keywords_from_model(self, limit: int = 2) -> list[str]:
        keywords = self.llm_service.generate_text(
            f"what are the best affiliate products to promote nowadays? Give me {limit} keywords to search for, separated by comma to be split into list of string in python, return keywords only"
        )
        keywords = keywords.split(",")
        return keywords

    def get_title(self, affiliate_link: AffiliateLink) -> str:
        try:
            prompt = f"Give me one post title about the category {affiliate_link.categories[0]} and the product title: {affiliate_link.product_title}, that is SEO friendly and time-agnostic, without directly mentioning the product, return the title only without quotes."
            return self.llm_service.generate_text(prompt)
        except Exception as e:
            self.logger.info(f"Error generating title: {e}")
            return f"{affiliate_link.categories[0]}"

    def execute_cron(self, custom_links: list[AffiliateLink] = []) -> None:
        keywords = self.keywords_map.get(self.program_name, [])

        for i, channel in enumerate(self.CHANNELS):
            channel_name = channel.__class__.__name__

            if not keywords:
                keywords = self.keywords_map.get(
                    channel_name, []
                ) or self.get_keywords_from_model(limit=3)

            affiliate_links = custom_links or self.get_affiliate_links(
                keywords=keywords
            )
            unused_links = self.media_service.get_unused_affiliate_links(
                affiliate_links
            )

            if not unused_links:
                self.logger.info(f"No unused affiliate links for {channel_name}.")
                continue

            for link in unused_links:
                try:
                    title = self.get_title(link)
                    image_urls = self.media_service.get_image_urls(
                        query=title, limit=len(self.CHANNELS)
                    )
                    create_fail_exist = False

                    try:
                        channel_name = channel.__class__.__name__
                        content_id = channel.create(
                            title=title,
                            image_url=image_urls[i] if image_urls else "",
                            affiliate_link=link,
                        )

                        if not content_id:
                            continue

                        self.logger.info(
                            f"[{channel_name}] content created (ID = {content_id}): {link.url}"
                        )
                    except Exception as e:
                        create_fail_exist = True
                        self.logger.error(
                            f"Error executing cron for channel {channel.__class__.__name__}: {e}"
                        )

                    if not create_fail_exist:
                        self.media_service.add_affiliate_link(link.url)
                except Exception as e:
                    self.logger.error(f"Error executing cron for link {link.url}: {e}")
