from amazon_paapi import models, AmazonApi

from affiliate_program import AffiliateProgram
from all_types import AffiliateLink

from common import os, load_dotenv


class VPNService(AffiliateProgram):
    IS_FIXED_LINK = True
    WORDPRESS_CREDENTIALS_SUFFIX = "VPN"

    def get_affiliate_links(self) -> list[AffiliateLink]:
        categories = ["vpn"]

        return [
            AffiliateLink(
                url="https://go.nordvpn.net/aff_c?offer_id=15&aff_id=131575&url_id=902",
                product_title="NordVPN",
                categories=categories,
            )
        ]
