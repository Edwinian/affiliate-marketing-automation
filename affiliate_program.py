from abc import ABC, abstractmethod
from channel import Channel
from common import os, load_dotenv

from all_types import AffiliateLink, CreateChannelResponse, UsedLink
from aws_service import AWSService
from enums import ChannelName
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
    WORDPRESS_NAV_MENU_ID = None
    CHANNEL = ChannelName.WORDPRESS.value

    def __init__(self):
        self.program_name = self.__class__.__name__
        log_name = self.program_name
        self.logger = LoggerService(name=log_name)
        self.llm_service = LlmService()
        self.media_service = MediaService()
        self.aws_service = AWSService()
        self.pinterest_service = PinterestService()
        self.wordpress = self.init_wordpress_service()
        self.channel_service_map: dict[ChannelName, Channel] = {
            ChannelName.WORDPRESS.value: self.wordpress,
            ChannelName.PINTEREST.value: self.pinterest_service,
        }

    @abstractmethod
    def get_affiliate_links(self) -> list[AffiliateLink]:
        """
        Abstract method to be implemented by subclasses for getting affiliate links from program.
        """
        pass

    def init_wordpress_service(self):
        credentials = {
            "API_URL": os.getenv(f"WORDPRESS_API_URL_{self.PROGRAM_KEY}"),
            "FRONTEND_URL": os.getenv(f"WORDPRESS_FRONTEND_URL_{self.PROGRAM_KEY}"),
            "ACCESS_TOKEN": os.getenv(f"WORDPRESS_ACCESS_TOKEN_{self.PROGRAM_KEY}"),
        }
        is_wordpress_hosted = False

        for key, value in credentials.items():
            if value is None:
                self.logger.warning(
                    f"Missing environment variable {key} for program {self.PROGRAM_KEY}, using wordpress-hosted credentials instead."
                )
                credentials = {
                    "API_URL": os.getenv(f"WORDPRESS_API_URL"),
                    "FRONTEND_URL": os.getenv(f"WORDPRESS_FRONTEND_URL"),
                    "ACCESS_TOKEN": os.getenv(f"WORDPRESS_ACCESS_TOKEN"),
                }
                is_wordpress_hosted = True
                break

        return WordpressService(
            credentials=credentials, is_wordpress_hosted=is_wordpress_hosted
        )

    def get_bulk_create_from_posts_csv(self, limit: int):
        posts = self.wordpress.get_posts()
        return self.pinterest_service.get_bulk_create_from_posts_csv(
            posts=posts, limit=limit
        )

    def create_content(self, affiliate_links: list[AffiliateLink]) -> list[UsedLink]:
        create_links: list[UsedLink] = []
        channel_service = self.channel_service_map[self.CHANNEL]

        for link in affiliate_links:
            try:
                new_content: CreateChannelResponse = channel_service.create(
                    affiliate_link=link,
                )

                if new_content:
                    post_id = (
                        new_content.id
                        if self.CHANNEL == ChannelName.WORDPRESS.value
                        else None
                    )
                    create_links.append(UsedLink(url=link.url, post_id=post_id))
                    self.logger.info(
                        f"[Content created (ID = {new_content.id}): {link.url}"
                    )
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

        create_links = self.create_content(affiliate_links=affiliate_links)

        if self.WORDPRESS_NAV_MENU_ID:
            self.wordpress.update_nav_menu(menu_id=self.WORDPRESS_NAV_MENU_ID)

        if not self.IS_FIXED_LINK:
            self.media_service.add_used_affiliate_links(used_links=create_links)

        return create_links
