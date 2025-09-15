from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramKey


class VPNService(AffiliateProgram):
    IS_FIXED_LINK = True
    PROGRAM_KEY = ProgramKey.VPN

    def get_affiliate_links(self) -> list[AffiliateLink]:
        categories = ["VPN"]

        return [
            AffiliateLink(
                url="https://go.nordvpn.net/aff_c?offer_id=15&aff_id=131575&url_id=902",
                product_title="NordVPN",
                categories=categories,
            )
        ]
