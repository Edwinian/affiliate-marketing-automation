import json
from llm_service import LlmService
from media_service import MediaService

llm_service = LlmService()
media_service = MediaService()


def is_valid_json(json_string):
    try:
        parsed_data = json.loads(json_string)
        return True, parsed_data, None
    except json.JSONDecodeError as e:
        return False, None, str(e)


def lambda_handler(event, context):
    try:
        body = event.get("body", "{}")
        if not isinstance(body, str):
            body = json.dumps(body)
        is_valid, parsed_data, error = is_valid_json(body)
        if not is_valid:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid JSON: {error}"}),
            }
        json_string = json.dumps(parsed_data, indent=2)
        niche = "fashion"
        prompt = f"Create a json string with value about {niche} that is SEO friendly and time-agnostic, response in json string only, json format like {json_string}"
        response = llm_service.generate_text(
            prompt=prompt,
        )
        return {"statusCode": 200, "body": json.dumps({"message": response})}
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to process request: {str(e)}"}),
        }


# Local test
if __name__ == "__main__":
    pin_data = {
        "board_id": "123456789",
        "title": "Sample Pin",
        "description": "This is a sample pin for testing",
        "link": "https://example.com",
        "media_source": {
            "source_type": "image_url",
            "url": "https://example.com/image.jpg",
            "content_type": "image/jpeg",
            "data": None,
        },
        "alt_text": "A sample image",
        "dominant_color": "#FF5733",
        "parent_pin_id": "987654321",
        "board_section_id": "456789123",
    }
    event = {"body": json.dumps(pin_data)}
    response = lambda_handler(event, None)
    print("response", response)
