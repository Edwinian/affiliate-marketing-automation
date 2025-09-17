from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramKey
from common import os, load_dotenv


class VPNService(AffiliateProgram):
    IS_FIXED_LINK = True
    PROGRAM_KEY = ProgramKey.VPN

    def get_affiliate_links(self) -> list[AffiliateLink]:
        categories = ["VPN"]
        products = [
            {
                "title": "NordVPN",
                "url": f"https://go.nordvpn.net/aff_c?offer_id=15&aff_id={os.getenv('NORD_VPN_AFFILIATE_ID')}&url_id=902",
                "cta_image_url": (
                    "https://edwinchan6.wordpress.com/wp-content/uploads/2025/09/affiliate-sales-campaign-1500x300-en-us.png",
                ),
            }
        ]
        affiliate_links = [
            AffiliateLink(
                url=prod["url"],
                product_title=prod["title"],
                categories=categories,
                cta_content=(
                    (
                        f'<a href="{prod["url"]}" target="_blank">'
                        f'<img src="{prod["cta_image_url"]}" alt="{prod["title"]} CTA" style="max-width: 100%; height: auto; display: block;">'
                        f"</a>"
                    )
                    if prod.get("cta_image_url", None)
                    else None
                ),
            )
            for prod in products
        ]

        return affiliate_links[: self.LINK_LIMIT]
