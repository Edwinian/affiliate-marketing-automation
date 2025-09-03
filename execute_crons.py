import time
from typing import Optional
from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from amazon_service import AmazonService
from enums import CustomLinksKey
from logger_service import LoggerService


def execute_crons(custom_links_map: Optional[dict[str, list[AffiliateLink]]] = None):
    logger = LoggerService(name="execute_crons")
    AMAZON_NICHES = ["beauty"]
    AMAZON_PROGRAMS = [AmazonService(niche=niche) for niche in AMAZON_NICHES]
    affiliate_programs: list[AffiliateProgram] = AMAZON_PROGRAMS

    for program in affiliate_programs:
        name = program.__class__.__name__
        logger.set_prefix(name)

        try:
            program_start_time = time.time()
            custom_links = (
                custom_links_map.get(program.CUSTOM_LINKS_KEY, [])
                if custom_links_map
                else []
            )

            # Execute the program's cron job
            program.execute_cron(custom_links=custom_links)

            program_end_time = time.time()
            execution_time = program_end_time - program_start_time
            logger.info(f"Finished execution of {name}: {execution_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error executing cron for {name}: {e}")


# Local test
if __name__ == "__main__":
    custom_links_map: dict[str, list[AffiliateLink]] = {
        CustomLinksKey.AMAZON: [
            # AffiliateLink(
            #     url="https://amzn.to/46d5C1d",
            #     product_title="Kasa Smart Plug HS103P4, Smart Home Wi-Fi Outlet Works with Alexa, Echo, Google Home & IFTTT, No Hub Required, Remote Control, 15 Amp, UL Certified, 4-Pack, White",
            #     categories=["Outlet Switches"],
            # ),
            # AffiliateLink(
            #     url="https://amzn.to/3JQsU56",
            #     product_title="Crest 3D Whitestrips Professional Effects – Teeth Whitening Kit, 22 Treatments (20 + 2 Bonus), Each with 1 Upper/1Lower, 44 Strips – Crest 3DWhite Teeth Whitening Strips",
            #     categories=["Strips"],
            # ),
            AffiliateLink(
                url="https://amzn.to/4oSGC7O",
                product_title="Physician's Choice Probiotics 60 Billion CFU - 10 Strains + Organic Prebiotics - Immune, Digestive & Gut Health - Supports Occasional Constipation, Diarrhea, Gas & Bloating - for Women & Men - 30ct",
                categories=["Acidophilus"],
            ),
            # AffiliateLink(
            #     url="https://amzn.to/45R2Tu7",
            #     product_title="Home-it Mop and Broom Holder Wall Mount Garden Tool Storage Tool Rack Storage & Organization for the Home Plastic Hanger for Closet Garage Organizer (5-position)",
            #     categories=["Storage Racks"],
            # ),
            # AffiliateLink(
            #     url="https://amzn.to/4lKnRAy",
            #     product_title="Amazon Basics Dog and Puppy Pee Pads, 5-Layer Leak-Proof Super Absorbent, Quick-Dry Surface, Potty Training, Regular (22x22), 100 Count, Blue & White",
            #     categories=["Disposable Training Pads"],
            # ),
        ]
    }
    execute_crons(custom_links_map=custom_links_map)

    # # Get CSV files for uploading pins
    # affiliate_programs: list[AffiliateProgram] = [AmazonService()]
    # pin_programs = [program for program in affiliate_programs if program.IS_PIN]
    # total_limit = 30

    # while total_limit > 0 and len(pin_programs) > 0:
    #     for program in pin_programs:
    #         if total_limit <= 0:
    #             break

    #         limit = max(1, total_limit // len(pin_programs))
    #         program.get_bulk_create_from_posts_csv(limit=limit)

    #         total_limit -= limit
