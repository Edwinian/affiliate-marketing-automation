import json


def execute(event, context):
    body = {"message": "Hello from AWS Lambda using Python", "input": event}
    response = {"statusCode": 200, "body": json.dumps(body)}
    return response
