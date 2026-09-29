terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  function_name = "${var.project_name}-${var.environment}"
  table_name    = "${var.project_name}-${var.environment}-tasks"
  log_group     = "/aws/lambda/${local.function_name}"
}

# --------------------------------------------------
# DynamoDB
# --------------------------------------------------

resource "aws_dynamodb_table" "tasks" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# --------------------------------------------------
# Package Lambda source code
# --------------------------------------------------

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/../lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

# --------------------------------------------------
# CloudWatch Logs
# --------------------------------------------------

resource "aws_cloudwatch_log_group" "lambda" {
  name              = local.log_group
  retention_in_days = 7

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# --------------------------------------------------
# Lambda
# --------------------------------------------------

resource "aws_lambda_function" "task_api" {
  function_name = local.function_name

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  role    = aws_iam_role.lambda.arn
  handler = "lambda_function.lambda_handler"

  runtime = "python3.11"

  timeout     = 10
  memory_size = 128

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.tasks.name
    }
  }

  # Structured JSON logging
  logging_config {
    log_format            = "JSON"
    application_log_level = "INFO"
    system_log_level      = "WARN"
    log_group             = aws_cloudwatch_log_group.lambda.name
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda
  ]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# --------------------------------------------------
# API Gateway HTTP API
# --------------------------------------------------

resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-${var.environment}-http-api"
  protocol_type = "HTTP"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# --------------------------------------------------
# API Gateway -> Lambda integration
# --------------------------------------------------

resource "aws_apigatewayv2_integration" "lambda" {
  api_id = aws_apigatewayv2_api.http.id

  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.task_api.invoke_arn
  integration_method = "POST"

  payload_format_version = "2.0"
}

# --------------------------------------------------
# API Routes
# --------------------------------------------------

resource "aws_apigatewayv2_route" "create_task" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /tasks"

  target = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "list_tasks" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /tasks"

  target = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "get_task" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /tasks/{id}"

  target = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "update_task" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "PUT /tasks/{id}"

  target = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "delete_task" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "DELETE /tasks/{id}"

  target = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# --------------------------------------------------
# API Gateway default stage
# --------------------------------------------------

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.http.id
  name   = "$default"

  auto_deploy = true

  # Basic request-rate protection
  default_route_settings {
    throttling_rate_limit  = 10
    throttling_burst_limit = 20
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# --------------------------------------------------
# Allow API Gateway to invoke Lambda
# --------------------------------------------------

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.task_api.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}