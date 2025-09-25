import time
from typing import Optional
from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from enums import ProgramBrand
from fiverr_service import FiverrService
from logger_service import LoggerService
from vpn_service import VPNService
from common import os, load_dotenv


def get_affiliate_programs() -> list[AffiliateProgram]:
    program_service_map: dict[str, AffiliateProgram] = {
        ProgramBrand.NORD: VPNService(),
        ProgramBrand.FIVERR: FiverrService(),
    }
    run_programs_str = os.getenv("RUN_PROGRAMS", "")
    run_programs = run_programs_str.split(",")
    affiliate_programs = [
        program_service_map.get(program, None) for program in run_programs
    ]
    affiliate_programs = [p for p in affiliate_programs if p is not None]
    return affiliate_programs


def execute_crons(
    custom_links_map: Optional[dict[str, list[AffiliateLink]]] = None,
):
    logger = LoggerService(name="execute_crons")
    affiliate_programs = get_affiliate_programs()

    logger.info(
        f"Programs to run: {[p.__class__.__name__ for p in affiliate_programs]}"
    )

    if not affiliate_programs:
        return

    for program in affiliate_programs:
        name = program.__class__.__name__
        logger.set_prefix(name)

        try:
            program_start_time = time.time()
            custom_links = (
                custom_links_map.get(program.PROGRAM_KEY, [])
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
        f"{ProgramBrand.AMAZON}_BEAUTY": [
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
    # pin_programs = [AmazonService()]
    # total_limit = 30

    # while total_limit > 0 and len(pin_programs) > 0:
    #     for program in pin_programs:
    #         if total_limit <= 0:
    #             break

    #         limit = max(1, total_limit // len(pin_programs))
    #         program.get_bulk_create_from_posts_csv(limit=limit)

    #         total_limit -= limit
