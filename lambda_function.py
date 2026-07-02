import json
import boto3
import uuid

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Tasks')

def lambda_handler(event, context):

    body = json.loads(event['body'])

    task = body['task']

    item = {
        'id': str(uuid.uuid4()),
        'task': task
    }

    table.put_item(Item=item)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Task added successfully'
        })
    }