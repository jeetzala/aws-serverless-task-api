output "api_endpoint" {
  description = "HTTP API endpoint."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "lambda_function_name" {
  description = "Lambda function name."
  value       = aws_lambda_function.task_api.function_name
}

output "dynamodb_table_name" {
  description = "DynamoDB table name."
  value       = aws_dynamodb_table.tasks.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group."
  value       = aws_cloudwatch_log_group.lambda.name
}

output "aws_region" {
  description = "AWS region used by the project."
  value       = var.aws_region
}