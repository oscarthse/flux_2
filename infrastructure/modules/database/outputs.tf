output "db_endpoint" {
  description = "The endpoint of the database"
  value       = aws_db_instance.main.endpoint
}

output "db_name" {
  description = "The name of the database"
  value       = aws_db_instance.main.db_name
}

output "db_username" {
  description = "The username for the database"
  value       = aws_db_instance.main.username
}
