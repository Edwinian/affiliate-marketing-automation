from abc import ABC, abstractmethod
from typing import List

from all_types import AffiliateLink, UsedLink
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
    IS_PIN = False
    PROGRAM_KEYWORDS_MAP: dict[str, list[str]] = {}
    WORDPRESS_CREDENTIALS: dict[str, str] = None

    def __init__(self):
        self.program_name = self.__class__.__name__
        log_name = self.program_name
        self.logger = LoggerService(name=log_name)
        self.llm_service = LlmService()
        self.media_service = MediaService()
        self.pinterest_service = PinterestService()

        if not self.WORDPRESS_CREDENTIALS:
            return self.logger.error("WORDPRESS_CREDENTIALS not set.")

        self.wordpress = WordpressService(credentials=self.WORDPRESS_CREDENTIALS)

    @abstractmethod
    def get_program_links(self, keywords: List[str]) -> list[AffiliateLink]:
        """
        Abstract method to be implemented by subclasses for getting affiliate links from program.
        """
        pass

    def get_bulk_create_from_posts_csv(self, limit: int):
        posts = self.wordpress.get_posts()
        return self.pinterest_service.get_bulk_create_from_posts_csv(
            posts=posts, limit=limit
        )

    def get_affiliate_links(
        self,
    ) -> list[AffiliateLink]:
        affiliate_links = []

        keywords = self.PROGRAM_KEYWORDS_MAP.get(self.program_name, [])

        if not keywords:
            keywords = (
                self.pinterest_service.get_keywords()
                if self.IS_PIN
                else self.get_keywords_from_model()
            )

        affiliate_links = self.get_program_links(keywords=keywords)
        affiliate_links = self.media_service.get_unused_affiliate_links(
            affiliate_links=affiliate_links
        )

        return affiliate_links

    def get_keywords_from_model(self, limit: int = 2) -> list[str]:
        keywords = self.llm_service.generate_text(
            f"what are the best affiliate products to promote nowadays? Give me {limit} keywords to search for, separated by comma to be split into list of string in python, return keywords only"
        )
        keywords = keywords.split(",")
        return keywords

    def create_content_for_links(
        self, affiliate_links: list[AffiliateLink]
    ) -> list[UsedLink]:
        create_links: list[UsedLink] = []
        link_images_map: dict[str, list[str]] = {}

        for link in affiliate_links:
            try:
                title = self.wordpress.get_title(link)
                image_urls = link_images_map.get(link.url, [])

                if not image_urls:
                    image_urls = self.media_service.get_image_urls(query=title)
                    link_images_map[link.url] = image_urls

                try:
                    new_post = self.wordpress.create(
                        title=title,
                        image_url=image_urls[0] if image_urls else "",
                        affiliate_link=link,
                    )

                    if new_post:
                        create_links.append(UsedLink(url=link.url, post_id=new_post.id))
                        self.logger.info(
                            f"[Post created (ID = {new_post.id}): {link.url}"
                        )
                except Exception as e:
                    self.logger.error(f"Error executing cron for Wordpress: {e}")
            except Exception as e:
                self.logger.error(f"Error executing cron for link {link.url}: {e}")

        return create_links

    def execute_cron(self, custom_links: list[AffiliateLink] = []) -> None:
        affiliate_links = custom_links or self.get_affiliate_links()

        if not affiliate_links:
            return self.logger.info(f"No custom or unused links.")

        create_links = self.create_content_for_links(affiliate_links=affiliate_links)
        self.wordpress.update_menu_items()
        self.media_service.add_used_affiliate_links(used_links=create_links)
