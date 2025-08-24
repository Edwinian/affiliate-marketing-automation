import time
import execute_crons


def lambda_handler(event, context):
    # Target duration: 10 minutes (600 seconds)
    target_duration = 600
    start_time = time.time()
    total_execution_time = 0

    while total_execution_time < target_duration:
        execute_crons()
        # Update total execution time after each full loop
        total_execution_time = time.time() - start_time

    return {"statusCode": 200}


# Local test
if __name__ == "__main__":
    response = lambda_handler(None, None)
    print("Response:", response)
