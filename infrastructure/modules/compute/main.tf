resource "aws_lambda_function" "main" {
  function_name = var.lambda_function_name
  role          = var.lambda_exec_role_arn

  filename         = var.zip_path
  handler          = var.handler
  runtime          = var.runtime
  memory_size      = var.memory_size
  timeout          = var.timeout

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.app_security_group_id]
  }

  source_code_hash = filebase64sha256(var.zip_path)
}
