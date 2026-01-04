output "api_endpoint" {
  description = "The endpoint of the API Gateway"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_id" {
  description = "The ID of the API Gateway"
  value       = aws_apigatewayv2_api.main.id
}
