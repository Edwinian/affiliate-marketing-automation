import time
from datetime import datetime, timedelta, timezone
from amazon_service import AmazonService
from channel_service import ChannelService
from media_service import MediaService
from pinterest_service import PinterestService
from wordpress_service import WordpressService


def lambda_handler(event, context):
    pinterest_service = PinterestService()
    # trends = pinterest_service.get_trends()
    trends = [
        "Bamboo T-shirts with custom embroidery",
        "smart thermostats with voice control",
        "reusable stainless steel water bottles",
        "wearable fitness trackers (smart rings)",
        "retro-inspired vinyl record players",
        "eco-friendly soy candles",
        "personalized engraved jewelry",
        "smart air purifiers",
        "sustainable meal prep containers",
        "mushroom coffee blends",
    ]
    trend_media_map: dict[str, MediaService] = {}
    # trend_amazon_map: dict[str, AmazonService] = {}

    # Fetch images for each trend
    for trend in trends:
        # amazon_service = AmazonService(query=trend)
        media_service = MediaService(query=trend)

        # trend_amazon_map[trend] = amazon_service
        trend_media_map[trend] = media_service

    # Repeat content creation for 10 minutes (in HKT, adjusted to UTC for Lambda)
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(minutes=10)
    channels: list[ChannelService] = [WordpressService()]
    create_count = {channel.__class__.__name__: 0 for channel in channels}

    while datetime.now(timezone.utc) < end_time:
        for trend in trends:
            for channel in channels:
                try:
                    # TODO: query for an affiliate link based on trend
                    # affiliate_link = trend_amazon_map[trend].get_affiliate_link()
                    affiliate_link = "https://example.com/affiliate-link"
                    image_url = trend_media_map[trend].get_image_url()

                    if not image_url:
                        print(f"No image found for trend: {trend}")
                        break  # Skip to next trend

                    content_id = channel.create(
                        image_url=image_url, trend=trend, affiliate_link=affiliate_link
                    )

                    if content_id:
                        print(
                            f"{channel.__class__.__name__}: CREATED CONTENT {content_id} for {trend}"
                        )
                        create_count[channel.__class__.__name__] += 1
                    else:
                        print(
                            f"Failed to create content for {trend} on {channel.__class__.__name__}"
                        )
                        continue
                except Exception as e:
                    print(
                        f"Error creating content for {trend} on {channel.__class__.__name__}: {e}"
                    )
                    continue

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

    message = ". ".join(
        f"{channel} create count: {count}" for channel, count in create_count.items()
    )
    return {"statusCode": 200, "body": f"{message}"}


# Local test
if __name__ == "__main__":
    response = lambda_handler(None, None)
    print("Response:", response)
