terraform {
  backend "s3" {
    bucket = "flux-terraform-state"
    key    = "flux.tfstate"
    region = "us-east-1"

    dynamodb_table = "flux-terraform-state-lock"
    encrypt        = true
  }
}
