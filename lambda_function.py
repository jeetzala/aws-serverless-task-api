import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "Tasks"))


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def get_body(event):
    body = event.get("body")

    if not body:
        return None

    if isinstance(body, str):
        return json.loads(body)

    return body


def lambda_handler(event, context):
    try:
        # Support both API Gateway payload formats.
        http_method = event.get("httpMethod")

        if not http_method:
            http_method = (
                event.get("requestContext", {})
                .get("http", {})
                .get("method", "POST")
            )

        http_method = http_method.upper()

        path_parameters = event.get("pathParameters") or {}

        # CREATE
        if http_method == "POST":
            body = get_body(event)

            if (
                not body
                or not isinstance(body.get("task"), str)
                or not body["task"].strip()
            ):
                return response(
                    400,
                    {
                        "error": "The 'task' field is required and cannot be empty."
                    }
                )

            task_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            item = {
                "id": task_id,
                "task": body["task"].strip(),
                "createdAt": timestamp,
                "updatedAt": timestamp
            }

            table.put_item(Item=item)

            return response(
                201,
                {
                    "message": "Task created successfully.",
                    "task": item
                }
            )

        # READ ALL
        if http_method == "GET" and not path_parameters.get("id"):
            result = table.scan()

            return response(
                200,
                {
                    "tasks": result.get("Items", [])
                }
            )

        # READ ONE
        if http_method == "GET" and path_parameters.get("id"):
            task_id = path_parameters["id"]

            result = table.get_item(
                Key={"id": task_id}
            )

            item = result.get("Item")

            if not item:
                return response(
                    404,
                    {
                        "error": "Task not found."
                    }
                )

            return response(
                200,
                {
                    "task": item
                }
            )

        # UPDATE
        if http_method == "PUT":
            task_id = path_parameters.get("id")

            if not task_id:
                return response(
                    400,
                    {
                        "error": "Task ID is required."
                    }
                )

            body = get_body(event)

            if (
                not body
                or not isinstance(body.get("task"), str)
                or not body["task"].strip()
            ):
                return response(
                    400,
                    {
                        "error": "The 'task' field is required and cannot be empty."
                    }
                )

            timestamp = datetime.now(timezone.utc).isoformat()

            try:
                result = table.update_item(
                    Key={"id": task_id},
                    UpdateExpression="SET #task = :task, updatedAt = :updatedAt",
                    ExpressionAttributeNames={
                        "#task": "task"
                    },
                    ExpressionAttributeValues={
                        ":task": body["task"].strip(),
                        ":updatedAt": timestamp
                    },
                    ConditionExpression="attribute_exists(id)",
                    ReturnValues="ALL_NEW"
                )

                return response(
                    200,
                    {
                        "message": "Task updated successfully.",
                        "task": result["Attributes"]
                    }
                )

            except ClientError as error:
                if (
                    error.response["Error"]["Code"]
                    == "ConditionalCheckFailedException"
                ):
                    return response(
                        404,
                        {
                            "error": "Task not found."
                        }
                    )

                raise

        # DELETE
        if http_method == "DELETE":
            task_id = path_parameters.get("id")

            if not task_id:
                return response(
                    400,
                    {
                        "error": "Task ID is required."
                    }
                )

            try:
                table.delete_item(
                    Key={"id": task_id},
                    ConditionExpression="attribute_exists(id)"
                )

                return response(
                    200,
                    {
                        "message": "Task deleted successfully."
                    }
                )

            except ClientError as error:
                if (
                    error.response["Error"]["Code"]
                    == "ConditionalCheckFailedException"
                ):
                    return response(
                        404,
                        {
                            "error": "Task not found."
                        }
                    )

                raise

        # UNSUPPORTED METHOD
        return response(
            405,
            {
                "error": "Method not allowed."
            }
        )

    except json.JSONDecodeError:
        return response(
            400,
            {
                "error": "Invalid JSON request body."
            }
        )

    except ClientError as error:
        print(f"DynamoDB error: {error}")

        return response(
            500,
            {
                "error": "Database operation failed."
            }
        )

    except Exception as error:
        print(f"Unexpected error: {error}")

        return response(
            500,
            {
                "error": "Internal server error."
            }
        )