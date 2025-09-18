from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramKey
from common import os, load_dotenv


class VPNService(AffiliateProgram):
    IS_FIXED_LINK = True
    PROGRAM_KEY = ProgramKey.VPN

    def get_affiliate_links(self) -> list[AffiliateLink]:
        categories = ["VPN"]
        affiliate_links = [
            AffiliateLink(
                url=f"https://go.nordvpn.net/aff_c?offer_id=15&aff_id={os.getenv('NORD_VPN_AFFILIATE_ID')}&url_id=902",
                product_title="NordVPN",
                categories=categories,
                cta_image_url="https://edwinchan6.wordpress.com/wp-content/uploads/2025/09/affiliate-sales-campaign-1500x300-en-us.png",
            )
        ]

        return affiliate_links[: self.LINK_LIMIT]
