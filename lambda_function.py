import time
from datetime import datetime, timedelta, timezone
from media_service import MediaService
from pinterest_service import PinterestService


def lambda_handler(event, context):
    # Initialize PinterestService
    pinterest_service = PinterestService()
    trends = pinterest_service.get_trends()
    trend_media_map: dict[str, MediaService] = {}

    # Fetch images for each trend
    for trend in trends:
        media_service = MediaService(query=trend)
        trend_media_map[trend] = media_service

    # Repeat pin creation for 10 minutes (in HKT, adjusted to UTC for Lambda)
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(minutes=10)
    pin_count = 0

    while datetime.now(timezone.utc) < end_time:
        for trend in trends:
            image_url = trend_media_map[trend].get_image_url()

            if not image_url:
                print(f"No Pinterest image found for trend: {trend}")
                continue  # Skip to next trend

            # Create pin
            pin_id = pinterest_service.create_pin(image_url=image_url, trend=trend)

            if pin_id:
                pin_count += 1
                print(f"Created pin {pin_id} for trend: {trend}")
            else:
                print(f"Failed to create pin for trend: {trend}")

            # Respect Pinterest and Pexels API rate limits, delay to prevent hitting rate limits
            time.sleep(1)

        # Short delay between cycles to avoid overwhelming APIs
        time.sleep(2)

        # Break if no images are available for any trend
        if all(
            trend_media_map[trend].used_image_count
            >= len(trend_media_map[trend].image_urls)
            for trend in trends
        ):
            print("No more images available for any trend.")
            break

    return {"statusCode": 200, "body": f"Created {pin_count} pins in 10 minutes."}


# Local test
if __name__ == "__main__":
    response = lambda_handler(None, None)
    print("Response:", response)
