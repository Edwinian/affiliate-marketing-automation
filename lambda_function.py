import time
from affiliate_program import AffiliateProgram
from all_types import AffiliateLink
from amazon_service import AmazonService
from enums import CustomLinksKey
from logger_service import LoggerService


def lambda_handler(event, context):
    logger = LoggerService(name="LambdaHandler")

    custom_links_map: dict[str, list[AffiliateLink]] = {CustomLinksKey.AMAZON: []}
    affiliate_programs: list[AffiliateProgram] = [
        AmazonService(query="trending products"),
    ]

    for program in affiliate_programs:
        name = program.__class__.__name__
        logger.set_prefix(name)

        try:
            start_time = time.time()
            name = program.__class__.__name__
            custom_links = custom_links_map.get(program.CUSTOM_LINKS_KEY, [])

            program.execute_cron(custom_links=custom_links)

            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"Finished execution of {name}: {execution_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error executing cron for {name}: {e}")

    return {"statusCode": 200}


# Local test
if __name__ == "__main__":
    response = lambda_handler(None, None)
    print("Response:", response)
