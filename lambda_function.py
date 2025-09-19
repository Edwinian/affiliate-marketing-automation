import time
from execute_crons import execute_crons
from logger_service import LoggerService
from common import os, load_dotenv


def lambda_handler(event, context):
    logger = LoggerService(name="lambda")
    start_time = time.time()

    execute_crons()

    total_execution_time = time.time() - start_time
    logger.info(f"Finished execution of: {total_execution_time:.2f} seconds")
    return {"statusCode": 200}


# Local test
if __name__ == "__main__":
    response = lambda_handler(None, None)
    print("Response:", response)
