from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramKey
from common import os, load_dotenv


class FiverrService(AffiliateProgram):
    IS_FIXED_LINK = True
    PROGRAM_KEY = ProgramKey.FIVERR
    FIVERR_CATEGORIES = [
        "Programming & Tech",
        "Digital Marketing",
        "Writing & Translation",
        "Video & Animation",
        "Music & Audio",
        "Business",
        "Lifestyle",
        "Data",
        "Gaming",
        "Mobile Apps",
    ]

    def _generate_gig_ads_widget(self) -> str:
        """Generate the Fiverr gig ads widget iframe."""
        return (
            f'<iframe src="https://www.fiverr.com/gig_widgets?id=U2FsdGVkX18zdGlcB7h1nvvHf7z82xlOIGyBKcb1AZTgFy8aaVsf/b5zLolbzVBbJUY5runH/U9bFJi+d7P9u9w2BThljiquOOLIswOe5CQ684eEm7QOgCaDnFRIbUK4TO9kl6CQLGZk0fwi5dXaU5ezvre3dULf17JC4cUoTbOMXpyR2U0uNKFqnjPriDjB/cevdhOAD41R5fNncqjHMUnZogHbbHBZ2nuu6mbSoyadxg+g3SXgBq1NotbEUQFPwW8vebTa0Z4cDo1dtW8fF1BwqBeYLnrqFTUYIOS7xm0HPHKABXVfYPeifsqhfIW39uRcasAwaHPNm+p4j3XjYo/uF1OL6/yAfz29fLWRwzK2gipvcjma0FpWh4UgUBXiZVpkhckcSaJ1P1qs+STkj3Urljf2P6sZDrEG7kjM3VF6Uex2oMKxTXng8f32SW+xqbqmYy6haD2GZcxtVvUH4w==&affiliate_id={os.getenv("FIVERR_AFFILIATE_ID")}&strip_google_tagmanager=true" '
            'loading="lazy" data-with-title="true" class="fiverr_nga_frame" frameborder="0" height="350" width="100%" '
            'referrerpolicy="no-referrer-when-downgrade" data-mode="random_gigs" '
            "onload=\"var frame = this; var script = document.createElement('script'); "
            "script.addEventListener('load', function() { window.FW_SDK.register(frame); }); "
            "script.setAttribute('src', 'https://www.fiverr.com/gig_widgets/sdk'); "
            'document.body.appendChild(script);" ></iframe>'
        )

    def get_affiliate_links(self) -> list[AffiliateLink]:
        """Generate a list of affiliate links for Fiverr services."""
        categories = ["Freelance"]
        gig_ads_widget = self._generate_gig_ads_widget()

        # Base affiliate link for general Fiverr marketplace
        affiliate_links = [
            AffiliateLink(
                url=f"https://www.fiverr.com/?utm_source={os.getenv("FIVERR_AFFILIATE_ID")}&utm_medium=cx_affiliate&utm_campaign=_bus-y&afp=&cxd_token=1144512_42729223&show_join=true",
                product_title=f"{cat} Freelance on Fiverr",
                categories=categories,
                cta_content=gig_ads_widget,
            )
            for cat in self.FIVERR_CATEGORIES
        ]
        referral_brand_title_map = {
            "fiverrmarketplace": "Fiverr Marketplace",
            "fp": "Fiverr Pro",
            "logomaker": "Fiverr Logo Maker",
            "fiverraffiliates": "Fiverr Affiliates",
        }
        referral_brands = list(referral_brand_title_map.keys())
        referral_links = [
            AffiliateLink(
                url=f"https://go.fiverr.com/visit/?bta={os.getenv("FIVERR_AFFILIATE_ID")}&brand={brand}",
                product_title=referral_brand_title_map[brand],
                categories=[referral_brand_title_map[brand]],
            )
            for brand in referral_brands
        ]

        return affiliate_links + referral_links
