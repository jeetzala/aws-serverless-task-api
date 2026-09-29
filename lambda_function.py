import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger()
logger.setLevel(logging.INFO)

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


def get_http_method(event):
    http_method = event.get("httpMethod")

    if not http_method:
        http_method = (
            event.get("requestContext", {})
            .get("http", {})
            .get("method", "POST")
        )

    return http_method.upper()


def get_path(event):
    return (
        event.get("rawPath")
        or event.get("path")
        or "/"
    )


def lambda_handler(event, context):
    try:
        http_method = get_http_method(event)
        path = get_path(event)
        path_parameters = event.get("pathParameters") or {}

        logger.info(
            "API request received",
            extra={
                "httpMethod": http_method,
                "path": path
            }
        )

        # CREATE
        if http_method == "POST":
            body = get_body(event)

            if (
                not body
                or not isinstance(body.get("task"), str)
                or not body["task"].strip()
            ):
                logger.warning("Invalid task creation request")

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

            logger.info(
                "Task created",
                extra={
                    "taskId": task_id
                }
            )

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

            logger.info(
                "Tasks listed",
                extra={
                    "taskCount": len(result.get("Items", []))
                }
            )

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
                logger.info(
                    "Task not found",
                    extra={
                        "taskId": task_id
                    }
                )

                return response(
                    404,
                    {
                        "error": "Task not found."
                    }
                )

            logger.info(
                "Task retrieved",
                extra={
                    "taskId": task_id
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
                logger.warning(
                    "Invalid task update request",
                    extra={
                        "taskId": task_id
                    }
                )

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

                logger.info(
                    "Task updated",
                    extra={
                        "taskId": task_id
                    }
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
                    logger.info(
                        "Task update failed because task was not found",
                        extra={
                            "taskId": task_id
                        }
                    )

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

                logger.info(
                    "Task deleted",
                    extra={
                        "taskId": task_id
                    }
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
                    logger.info(
                        "Task deletion failed because task was not found",
                        extra={
                            "taskId": task_id
                        }
                    )

                    return response(
                        404,
                        {
                            "error": "Task not found."
                        }
                    )

                raise

        logger.warning(
            "Unsupported HTTP method",
            extra={
                "httpMethod": http_method,
                "path": path
            }
        )

        return response(
            405,
            {
                "error": "Method not allowed."
            }
        )

    except json.JSONDecodeError:
        logger.warning("Invalid JSON request")

        return response(
            400,
            {
                "error": "Invalid JSON request body."
            }
        )

    except ClientError as error:
        logger.exception("DynamoDB operation failed")

        return response(
            500,
            {
                "error": "Database operation failed."
            }
        )

    except Exception:
        logger.exception("Unexpected Lambda error")

        return response(
            500,
            {
                "error": "Internal server error."
            }
        )