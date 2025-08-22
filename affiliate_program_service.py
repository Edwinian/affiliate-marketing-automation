from abc import ABC, abstractmethod
from typing import Optional

from all_types import AffiliateLink
from enums import CustomLinksKey


class AffiliateProgramService(ABC):
    """
    Base class for affiliate program services that need to execute cron jobs.
    """

    CUSTOM_LINKS_KEY = CustomLinksKey.DEFAULT

    @abstractmethod
    def get_affiliate_link(self) -> AffiliateLink:
        """
        Abstract method to be implemented by subclasses for getting affiliate link.
        """
        pass

    @abstractmethod
    def execute_cron(self, custom_links: Optional[list[AffiliateLink]] = []) -> None:
        """
        Abstract method to be implemented by subclasses for executing cron jobs.
        """
        pass
