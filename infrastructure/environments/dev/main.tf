terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}

module "network" {
  source = "../../modules/network"

  project_name = "flux"
  environment  = "dev"
}

module "database" {
  source = "../../modules/database"

  project_name          = "flux"
  environment           = "dev"
  db_name               = "flux_dev"
  db_username           = "flux"
  db_password           = "fluxpassword" # Replace with a secret in a real environment
  db_instance_class     = "db.t3.micro"
  vpc_id                = module.network.vpc_id
  private_subnet_ids    = module.network.private_subnet_ids
  app_security_group_id = module.network.app_security_group_id
}

module "storage" {
  source = "../../modules/storage"

  project_name = "flux"
  environment  = "dev"
}

module "iam" {
  source = "../../modules/iam"

  project_name         = "flux"
  environment          = "dev"
  lambda_function_name = "flux-dev-api"
}

module "compute" {
  source = "../../modules/compute"

  project_name          = "flux"
  environment           = "dev"
  lambda_function_name  = "flux-dev-api"
  lambda_exec_role_arn  = module.iam.lambda_exec_role_arn
  app_security_group_id = module.network.app_security_group_id
  private_subnet_ids    = module.network.private_subnet_ids
  zip_path              = "../../../../dist/api/dummy.zip"
}

module "api" {
  source = "../../modules/api"

  project_name         = "flux"
  environment          = "dev"
  lambda_function_arn  = module.compute.lambda_function_arn
  lambda_function_name = module.compute.lambda_function_name
}
