from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramBrand
from common import os, load_dotenv


class FiverrService(AffiliateProgram):
    IS_FIXED_LINK = True
    PROGRAM_KEY = ProgramBrand.FIVERR
    FIVERR_CATEGORIES = [
        {
            "title": "Programming & Tech",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816550",
        },
        # {
        #     "title": "Digital Marketing",
        #     "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599",
        # },
        # {
        #     "title": "Video & Animation",
        #     "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599",
        # },
        {
            "title": "Music & Audio",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599",
        },
        # {"title": "Business", "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599"},
        # {"title": "Finance", "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599"},
        {
            "title": "Graphics & Design",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816574",
        },
        {
            "title": "Photography",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599",
        },
        # {"title": "Consulting", "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599"},
        {
            "title": "Mobile Apps",
            "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816567",
        },
    ]
    REFERRAL_BRANDS = [
        # {
        #     "param": "fiverrmarketplace",
        #     "title": "Fiverr Marketplace",
        #     "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816599",
        # },
        # {
        #     "param": "fp",
        #     "title": "Fiverr Pro",
        #     "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816713",
        # },
        # {
        #     "param": "logomaker",
        #     "title": "Fiverr Logo Maker",
        #     "cta_image_url": "https://fiverr.ck-cdn.com/tn/serve/?cid=42816561",
        # },
        # {
        #     "param": "fiverraffiliates",
        #     "title": "Fiverr Sub Affiliates",
        #     "cta_image_url": "https://edwinchan6.wordpress.com/wp-content/uploads/2025/09/fiverr-subaffiliates-cta-banner.jpg",
        # },
    ]

    def get_affiliate_links(self) -> list[AffiliateLink]:
        """Generate a list of affiliate links for Fiverr services."""
        affiliate_links = [
            AffiliateLink(
                url=f"https://www.fiverr.com/?utm_source=1144512&utm_medium=cx_affiliate&utm_campaign=_bus-y&afp=&cxd_token=1144512_42729223&show_join=true",
                product_title=f"{cat['title']} freelance hiring",
                categories=[cat["title"], "Gigs"],
                cta_image_url=cat.get("cta_image_url", None),
                cta_btn_text="Explore Gigs on Fiverr",
            )
            for cat in self.FIVERR_CATEGORIES
        ]
        referral_links = [
            AffiliateLink(
                url=f"https://go.fiverr.com/visit/?bta=1144512&brand={brand['param']}",
                product_title=brand["title"],
                categories=[brand["title"]],
                cta_image_url=brand["cta_image_url"],
            )
            for brand in self.REFERRAL_BRANDS
        ]

        return affiliate_links + referral_links
