from abc import ABC, abstractmethod
from typing import Optional

from all_types import AffiliateLink
from channel_service import ChannelService
from enums import CustomLinksKey
from llm_service import LlmService
from media_service import MediaService
from pinterest_service import PinterestService
from wordpress_service import WordpressService


class AffiliateProgramService(ABC):
    """
    Base class for affiliate program services that need to execute cron jobs.
    """

    CUSTOM_LINKS_KEY = CustomLinksKey.DEFAULT
    CHANNELS: list[ChannelService] = [WordpressService, PinterestService]

    def __init__(self):
        self.llm_service = LlmService()
        self.media_service = MediaService()
        self.wordpress_service = WordpressService()

    @abstractmethod
    def get_affiliate_links(self) -> list[AffiliateLink]:
        """
        Abstract method to be implemented by subclasses for getting affiliate link.
        """
        pass

    def get_title(self, affiliate_link: AffiliateLink) -> str:
        try:
            prompt = f"I make a website about {','.join(affiliate_link.categories)}. Give me one title based on {affiliate_link.url} that is SEO friendly and time-agnostic, return the title only."
            return self.llm_service.generate_text(prompt)
        except Exception as e:
            print(f"Error generating title: {e}")
            return f"{affiliate_link.categories[0]}"

    def execute_cron(self, custom_links: list[AffiliateLink] = []) -> None:
        affiliate_links = custom_links or self.get_affiliate_links()

        if not affiliate_links:
            print("No affiliate links available.")
            return

        unused_links = [
            link
            for link in affiliate_links
            if not self.media_service.is_affiliate_link_used(link.url)
        ]

        if not unused_links:
            print("All affiliate links have been used, retry")
            return self.execute_cron()

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
                        print(
                            f"[{channel.__class__.__name__}] content created (ID = {content_id}): {link.url}"
                        )
                    except Exception as e:
                        print(
                            f"Error executing cron for channel {channel.__name__}: {e}"
                        )

                self.media_service.add_affiliate_link(link.url)
            except Exception as e:
                print(f"Error executing cron for link {link.url}: {e}")
