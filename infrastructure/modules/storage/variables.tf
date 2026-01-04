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
