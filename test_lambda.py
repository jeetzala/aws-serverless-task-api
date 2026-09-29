import json

import lambda_function
from botocore.exceptions import ClientError


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[Item["id"]] = Item

    def scan(self):
        return {
            "Items": list(self.items.values())
        }

    def get_item(self, Key):
        item = self.items.get(Key["id"])

        if item:
            return {
                "Item": item
            }

        return {}

    def update_item(
        self,
        Key,
        UpdateExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
        ConditionExpression,
        ReturnValues,
    ):
        task_id = Key["id"]

        if task_id not in self.items:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ConditionalCheckFailedException",
                        "Message": "The conditional request failed"
                    }
                },
                "UpdateItem"
            )

        item = self.items[task_id]

        item["task"] = ExpressionAttributeValues[":task"]
        item["updatedAt"] = ExpressionAttributeValues[":updatedAt"]

        return {
            "Attributes": item
        }

    def delete_item(self, Key, ConditionExpression):
        task_id = Key["id"]

        if task_id not in self.items:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ConditionalCheckFailedException",
                        "Message": "The conditional request failed"
                    }
                },
                "DeleteItem"
            )

        del self.items[task_id]


# Replace the real DynamoDB table with our local fake table.
lambda_function.table = FakeTable()


def run_test(name, event):
    result = lambda_function.lambda_handler(event, None)

    print(f"\n{name}")
    print(f"Status: {result['statusCode']}")
    print(f"Body:   {result['body']}")

    return result


# --------------------------------------------------
# 1. CREATE
# --------------------------------------------------

create_result = run_test(
    "POST /tasks",
    {
        "httpMethod": "POST",
        "body": json.dumps({
            "task": "Learn AWS Serverless"
        })
    }
)

assert create_result["statusCode"] == 201

create_body = json.loads(create_result["body"])

task_id = create_body["task"]["id"]

assert create_body["task"]["task"] == "Learn AWS Serverless"
assert "createdAt" in create_body["task"]
assert "updatedAt" in create_body["task"]


# --------------------------------------------------
# 2. GET ALL
# --------------------------------------------------

get_all_result = run_test(
    "GET /tasks",
    {
        "httpMethod": "GET",
        "pathParameters": None
    }
)

assert get_all_result["statusCode"] == 200

get_all_body = json.loads(get_all_result["body"])

assert len(get_all_body["tasks"]) == 1


# --------------------------------------------------
# 3. GET ONE
# --------------------------------------------------

get_one_result = run_test(
    "GET /tasks/{id}",
    {
        "httpMethod": "GET",
        "pathParameters": {
            "id": task_id
        }
    }
)

assert get_one_result["statusCode"] == 200

get_one_body = json.loads(get_one_result["body"])

assert get_one_body["task"]["id"] == task_id
assert get_one_body["task"]["task"] == "Learn AWS Serverless"


# --------------------------------------------------
# 4. UPDATE EXISTING TASK
# --------------------------------------------------

update_result = run_test(
    "PUT /tasks/{id}",
    {
        "httpMethod": "PUT",
        "pathParameters": {
            "id": task_id
        },
        "body": json.dumps({
            "task": "Learn AWS Serverless and DynamoDB"
        })
    }
)

assert update_result["statusCode"] == 200

update_body = json.loads(update_result["body"])

assert update_body["task"]["task"] == (
    "Learn AWS Serverless and DynamoDB"
)


# --------------------------------------------------
# 5. UPDATE NONEXISTENT TASK
# --------------------------------------------------

update_missing_result = run_test(
    "PUT nonexistent task",
    {
        "httpMethod": "PUT",
        "pathParameters": {
            "id": "does-not-exist"
        },
        "body": json.dumps({
            "task": "This should fail"
        })
    }
)

assert update_missing_result["statusCode"] == 404


# --------------------------------------------------
# 6. INVALID CREATE REQUEST
# --------------------------------------------------

invalid_create_result = run_test(
    "POST invalid task",
    {
        "httpMethod": "POST",
        "body": json.dumps({
            "task": ""
        })
    }
)

assert invalid_create_result["statusCode"] == 400


# --------------------------------------------------
# 7. INVALID JSON
# --------------------------------------------------

invalid_json_result = run_test(
    "POST invalid JSON",
    {
        "httpMethod": "POST",
        "body": "{invalid-json}"
    }
)

assert invalid_json_result["statusCode"] == 400


# --------------------------------------------------
# 8. DELETE EXISTING TASK
# --------------------------------------------------

delete_result = run_test(
    "DELETE /tasks/{id}",
    {
        "httpMethod": "DELETE",
        "pathParameters": {
            "id": task_id
        }
    }
)

assert delete_result["statusCode"] == 200


# --------------------------------------------------
# 9. GET DELETED TASK
# --------------------------------------------------

get_deleted_result = run_test(
    "GET deleted task",
    {
        "httpMethod": "GET",
        "pathParameters": {
            "id": task_id
        }
    }
)

assert get_deleted_result["statusCode"] == 404


# --------------------------------------------------
# 10. DELETE NONEXISTENT TASK
# --------------------------------------------------

delete_missing_result = run_test(
    "DELETE nonexistent task",
    {
        "httpMethod": "DELETE",
        "pathParameters": {
            "id": "does-not-exist"
        }
    }
)

assert delete_missing_result["statusCode"] == 404


# --------------------------------------------------
# 11. UNSUPPORTED METHOD
# --------------------------------------------------

unsupported_result = run_test(
    "PATCH /tasks",
    {
        "httpMethod": "PATCH",
        "pathParameters": None
    }
)

assert unsupported_result["statusCode"] == 405


# --------------------------------------------------
# 12. API GATEWAY HTTP API PAYLOAD FORMAT 2.0
# --------------------------------------------------

lambda_v2_result = run_test(
    "HTTP API v2 POST /tasks",
    {
        "version": "2.0",
        "routeKey": "POST /tasks",
        "rawPath": "/tasks",
        "requestContext": {
            "http": {
                "method": "POST"
            }
        },
        "body": json.dumps({
            "task": "Test API Gateway HTTP API v2"
        })
    }
)

assert lambda_v2_result["statusCode"] == 201

lambda_v2_body = json.loads(lambda_v2_result["body"])

assert lambda_v2_body["task"]["task"] == (
    "Test API Gateway HTTP API v2"
)


print("\n✅ All CRUD, validation, and HTTP API v2 tests passed successfully.")