output "app_data_bucket_id" {
  description = "The ID of the app data bucket"
  value       = aws_s3_bucket.app_data.id
}

output "app_data_bucket_arn" {
  description = "The ARN of the app data bucket"
  value       = aws_s3_bucket.app_data.arn
}

output "logs_bucket_id" {
  description = "The ID of the logs bucket"
  value       = aws_s3_bucket.logs.id
}

output "logs_bucket_arn" {
  description = "The ARN of the logs bucket"
  value       = aws_s3_bucket.logs.arn
}
