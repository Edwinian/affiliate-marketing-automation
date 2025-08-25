import time
from typing import Optional
from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from amazon_service import AmazonService
from enums import CustomLinksKey
from logger_service import LoggerService


def execute_crons(custom_links_map: Optional[dict[str, list[AffiliateLink]]] = None):
    logger = LoggerService(name="execute_crons")
    affiliate_programs: list[AffiliateProgram] = [AmazonService()]

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
            #     categories=["Home Improvement"],
            # ),
            # AffiliateLink(
            #     url="https://amzn.to/3JQsU56",
            #     categories=["Health & Personal Care"],
            # ),
            AffiliateLink(
                url="https://amzn.to/4oSGC7O",
                categories=["Health & Personal Care"],
            ),
            AffiliateLink(
                url="https://amzn.to/45R2Tu7",
                categories=["Home Improvement"],
            ),
            AffiliateLink(
                url="https://amzn.to/4lKnRAy",
                categories=["Pet Supplies"],
            ),
        ]
    }
    response = execute_crons(custom_links_map=custom_links_map)
    print("Response:", response)
