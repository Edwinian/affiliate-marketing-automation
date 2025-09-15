import time
import execute_crons
from logger_service import LoggerService


def lambda_handler(event, context):
    logger = LoggerService(name="lambda")

    # Target duration: 10 minutes (600 seconds)
    target_duration = 600
    start_time = time.time()
    total_execution_time = 0

    while total_execution_time < target_duration:
        execute_crons()
        total_execution_time = time.time() - start_time

    logger.info(f"Finished execution of: {total_execution_time:.2f} seconds")
    return {"statusCode": 200}


# Local test
if __name__ == "__main__":
    response = lambda_handler(None, None)
    print("Response:", response)
