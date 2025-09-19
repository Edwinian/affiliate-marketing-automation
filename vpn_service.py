from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramKey
from common import os, load_dotenv


class VPNService(AffiliateProgram):
    IS_FIXED_LINK = True
    PROGRAM_KEY = ProgramKey.VPN

    def get_affiliate_links(self) -> list[AffiliateLink]:
        comparison_image_url = "https://webshielddaily.com/wp-content/uploads/2025/09/nordvpn_comparison.png"
        comparison_report_url = "https://webshielddaily.com/wp-content/uploads/2025/09/AV-TEST_NordVPN_Comparative_Test_Report_September_2020.pdf"
        affiliate_links = [
            AffiliateLink(
                url=f"https://go.nordvpn.net/aff_c?offer_id=15&aff_id={os.getenv('NORD_VPN_AFFILIATE_ID')}&url_id=902",
                product_title="NordVPN",
                categories=["VPN"],
                cta_image_url="https://webshielddaily.com/wp-content/uploads/2025/09/affiliate-sales-campaign-1500x300-en-us.png",
                additional_content=f'<div><img src="{comparison_image_url}" alt="NordVPN Comparison" style="max-width: 100%; height: auto; display: block;"></div><div style="text-align: center;"><div>Date of comparison: January 11, 2024.</div><div>*Overall network performance according to research by AV-Test. You can read <a href="{comparison_report_url}" target="_blank">the full report</a>.</div></div>',
            ),
            AffiliateLink(
                url=f"https://go.nordpass.io/aff_c?offer_id=488&aff_id={os.getenv('NORD_VPN_AFFILIATE_ID')}&url_id=9356 ",
                product_title="NordPass",
                categories=["Password Manager"],
                cta_image_url="https://webshielddaily.com/wp-content/uploads/2025/09/affiliate-august-sales-campaign-1500x300-1.png",
            ),
        ]

        return affiliate_links[: self.LINK_LIMIT]
