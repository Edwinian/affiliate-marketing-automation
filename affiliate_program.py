from abc import ABC, abstractmethod
from common import os, load_dotenv
from typing import List, Optional

from all_types import AffiliateLink, UsedLink
from aws_service import AWSService
from enums import ProgramKey
from llm_service import LlmService
from logger_service import LoggerService
from media_service import MediaService
from pinterest_service import PinterestService
from wordpress_service import WordpressService


class AffiliateProgram(ABC):
    """
    Base class for affiliate program services that need to execute cron jobs.
    """

    PROGRAM_KEY = None
    IS_FIXED_LINK: bool = False
    LINK_LIMIT = 1

    def __init__(self):
        self.program_name = self.__class__.__name__
        log_name = self.program_name
        self.logger = LoggerService(name=log_name)
        self.llm_service = LlmService()
        self.media_service = MediaService()
        self.aws_service = AWSService()
        self.pinterest_service = PinterestService()

        self.WORDPRESS_CREDENTIALS = {
            "API_URL": os.getenv(f"WORDPRESS_API_URL_{self.PROGRAM_KEY}"),
            "FRONTEND_URL": os.getenv(f"WORDPRESS_FRONTEND_URL_{self.PROGRAM_KEY}"),
            "ACCESS_TOKEN": os.getenv(f"WORDPRESS_ACCESS_TOKEN_{self.PROGRAM_KEY}"),
        }

        for key, value in self.WORDPRESS_CREDENTIALS.items():
            if value is None:
                self.logger.error(
                    f"Missing environment variable for {key}: WORDPRESS_{key}_{self.PROGRAM_KEY}"
                )
                return

        self.wordpress = WordpressService(credentials=self.WORDPRESS_CREDENTIALS)

    @abstractmethod
    def get_affiliate_links(self) -> list[AffiliateLink]:
        """
        Abstract method to be implemented by subclasses for getting affiliate links from program.
        """
        pass

    def get_bulk_create_from_posts_csv(self, limit: int):
        posts = self.wordpress.get_posts()
        return self.pinterest_service.get_bulk_create_from_posts_csv(
            posts=posts, limit=limit
        )

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
        all_posts = self.wordpress.get_posts()

        for link in affiliate_links:
            try:
                category_titles = [
                    post.title
                    for post in all_posts
                    if post.categories
                    and any(
                        link_cat
                        for link_cat in link.categories
                        if link_cat in [cat.name for cat in post.categories]
                    )
                ]
                title = self.wordpress.get_title(
                    affiliate_link=link, category_titles=category_titles
                )

                try:
                    new_post = self.wordpress.create(
                        title=title,
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
        affiliate_links = (
            self.media_service.get_unused_affiliate_links(affiliate_links=custom_links)
            or self.get_affiliate_links()
        )

        if not affiliate_links:
            return self.logger.info(f"No custom or unused links.")

        create_links = self.create_content_for_links(affiliate_links=affiliate_links)

        if not self.IS_FIXED_LINK:
            self.media_service.add_used_affiliate_links(used_links=create_links)
