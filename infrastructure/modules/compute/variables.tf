variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "flux"
}

variable "environment" {
  description = "Environment (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "lambda_exec_role_arn" {
  description = "ARN of the Lambda execution role"
  type        = string
}

variable "app_security_group_id" {
  description = "ID of the application security group"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of IDs of private subnets"
  type        = list(string)
}

variable "handler" {
  description = "Handler for the Lambda function"
  type        = string
  default     = "main.handler"
}

variable "runtime" {
  description = "Runtime for the Lambda function"
  type        = string
  default     = "python3.12"
}

variable "memory_size" {
  description = "Memory size for the Lambda function"
  type        = number
  default     = 128
}

variable "timeout" {
  description = "Timeout for the Lambda function"
  type        = number
  default     = 30
}

variable "zip_path" {
  description = "Path to the zip file for the Lambda function"
  type        = string
}
