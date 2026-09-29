variable "aws_region" {
  description = "AWS region for the serverless application."
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Project name used for AWS resource naming."
  type        = string
  default     = "serverless-task-api"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}