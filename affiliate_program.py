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
        # PinterestService(), # Creating max 30 pins per week only, so cron job is not needed
    ]
    PROGRAM_KEYWORDS_MAP: dict[str, list[str]] = {}
    IS_PIN = False

    def __init__(self):
        self.program_name = self.__class__.__name__
        log_name = self.program_name
        self.logger = LoggerService(name=log_name)
        self.llm_service = LlmService()
        self.media_service = MediaService()
        self.pinterest_service = PinterestService()

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
        affiliate_links = custom_links
        link_images_map: dict[str, list[str]] = {}

        for i, channel in enumerate(self.CHANNELS):
            created_link_urls: list[str] = []
            channel_name = channel.__class__.__name__
            self.logger.set_prefix(channel_name)

            if not affiliate_links:
                keywords = self.PROGRAM_KEYWORDS_MAP.get(self.program_name, [])

                if not keywords:
                    keywords = (
                        self.pinterest_service.get_keywords()
                        if self.IS_PIN
                        else channel.get_keywords()
                    )

                affiliate_links = self.get_affiliate_links(keywords=keywords)

            unused_links = self.media_service.get_unused_affiliate_links(
                affiliate_links=affiliate_links, channel_name=channel_name
            )

            if not unused_links:
                self.logger.info(f"No unused affiliate links.")
                continue

            for link in unused_links:
                try:
                    title = self.get_title(link)
                    image_urls = link_images_map.get(link.url, [])

                    if not image_urls:
                        image_urls = self.media_service.get_image_urls(
                            query=title, limit=len(self.CHANNELS)
                        )
                        link_images_map[link.url] = image_urls

                    try:
                        new_content = channel.create(
                            title=title,
                            image_url=image_urls[i] if image_urls else "",
                            affiliate_link=link,
                        )

                        if new_content:
                            created_link_urls.append(link.url)
                            self.logger.info(
                                f"[Content created (ID = {new_content.id}): {link.url}"
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error executing cron for channel {channel.__class__.__name__}: {e}"
                        )
                except Exception as e:
                    self.logger.error(f"Error executing cron for link {link.url}: {e}")

            self.media_service.add_affiliate_links(
                channel_name=channel_name, urls=created_link_urls
            )
