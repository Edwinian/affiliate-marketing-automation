import json
import pyjokes  # Example dependency


def lambda_handler(event, context):
    joke = pyjokes.get_joke()
    body = {"message": f"Hello from AWS Lambda! Here's a joke: {joke}", "input": event}
    return {"statusCode": 200, "body": json.dumps(body)}
