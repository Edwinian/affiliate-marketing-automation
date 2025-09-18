from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramKey
from common import os, load_dotenv


class FiverrService(AffiliateProgram):
    IS_FIXED_LINK = True
    PROGRAM_KEY = ProgramKey.FIVERR
    FIVERR_CATEGORIES = [
        {
            "title": "Programming & Tech",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816550",
        },
        {
            "title": "Digital Marketing",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816574",
        },
        {"title": "Writing & Translation", "cta_image_url": None},
        {"title": "Video & Animation", "cta_image_url": None},
        {"title": "Music & Audio", "cta_image_url": None},
        {"title": "Business", "cta_image_url": None},
        {"title": "Lifestyle", "cta_image_url": None},
        {"title": "Data", "cta_image_url": None},
        {"title": "Gaming", "cta_image_url": None},
        {
            "title": "Mobile Apps",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816567",
        },
    ]
    REFERRAL_BRAND_TITLE_MAP = {
        "fiverrmarketplace": {
            "title": "Fiverr Marketplace",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599",
        },
        "fp": {
            "title": "Fiverr Pro",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816713",
        },
        "logomaker": {
            "title": "Logo Maker",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816561",
        },
        "fiverraffiliates": {
            "title": "Fiverr Sub Affiliates",
            "cta_image_url": "https://edwinchan6.wordpress.com/wp-content/uploads/2025/09/fiverr-subaffiliates-cta-banner.jpg",
        },
    }

    def get_affiliate_links(self) -> list[AffiliateLink]:
        """Generate a list of affiliate links for Fiverr services."""
        # Base affiliate link for general Fiverr marketplace
        affiliate_links = [
            AffiliateLink(
                url=f"https://www.fiverr.com/?utm_source={os.getenv("FIVERR_AFFILIATE_ID")}&utm_medium=cx_affiliate&utm_campaign=_bus-y&afp=&cxd_token={os.getenv("FIVERR_AFFILIATE_ID")}_42729223&show_join=true",
                product_title=f"{cat['title']} Freelance on Fiverr",
                categories=[cat["title"], "Freelance"],
                cta_image_url=cat.get("cta_image_url", None),
                cta_btn_text="Explore Gigs on Fiverr",
            )
            for cat in self.FIVERR_CATEGORIES
        ]
        referral_brands = list(self.REFERRAL_BRAND_TITLE_MAP.keys())
        referral_links = [
            AffiliateLink(
                url=f"https://go.fiverr.com/visit/?bta={os.getenv("FIVERR_AFFILIATE_ID")}&brand={brand}",
                product_title=self.REFERRAL_BRAND_TITLE_MAP[brand]["title"],
                categories=[self.REFERRAL_BRAND_TITLE_MAP[brand]["title"]],
                cta_image_url=self.REFERRAL_BRAND_TITLE_MAP[brand].get(
                    "cta_image_url", None
                ),
            )
            for brand in referral_brands
        ]

        return affiliate_links + referral_links
