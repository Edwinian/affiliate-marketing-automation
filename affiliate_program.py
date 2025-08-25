from abc import ABC, abstractmethod

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
        PinterestService(),
    ]

    def __init__(self):
        log_name = self.__class__.__name__
        self.logger = LoggerService(name=log_name)
        self.llm_service = LlmService()
        self.media_service = MediaService()

    @abstractmethod
    def get_affiliate_links(self, limit: int = 5) -> list[AffiliateLink]:
        """
        Abstract method to be implemented by subclasses for getting affiliate link.
        """
        pass

    def get_title(self, affiliate_link: AffiliateLink) -> str:
        try:
            prompt = f"I make a website about {','.join(affiliate_link.categories[0])}. Give me one title based on {affiliate_link.url} that is SEO friendly and time-agnostic, return the title only."
            return self.llm_service.generate_text(prompt)
        except Exception as e:
            self.logger.info(f"Error generating title: {e}")
            return f"{affiliate_link.categories[0]}"

    def execute_cron(self, custom_links: list[AffiliateLink] = []) -> None:
        affiliate_links = custom_links + self.get_affiliate_links()
        unused_links = self.media_service.get_unused_affiliate_links(affiliate_links)

        if not unused_links:
            self.logger.warning("No affiliate links available.")
            return

        for link in unused_links:
            try:
                title = self.get_title(link)
                image_urls = self.media_service.get_image_urls(
                    query=title, limit=len(self.CHANNELS)
                )

                for i, channel in enumerate(self.CHANNELS):
                    try:
                        content_id = channel.create(
                            title=title,
                            image_url=image_urls[i] if image_urls else "",
                            affiliate_link=link,
                        )
                        self.logger.info(
                            f"[{channel.__class__.__name__}] content created (ID = {content_id}): {link.url}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error executing cron for channel {channel.__name__}: {e}"
                        )

                self.media_service.add_affiliate_link(link.url)
            except Exception as e:
                self.logger.error(f"Error executing cron for link {link.url}: {e}")
