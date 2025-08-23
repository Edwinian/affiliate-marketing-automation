from abc import ABC, abstractmethod

from all_types import AffiliateLink


class ChannelService(ABC):
    DISCLOSURE = "Disclosure: At no cost to you, I may earn a small commission from qualifying purchases made through links here. This income helps support creating more content for you. Thank you for your support!"

    @abstractmethod
    def create(self, title: str, image_url: str, affiliate_link: AffiliateLink) -> str:
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
