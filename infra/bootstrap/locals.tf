locals {
  aws_region          = "us-east-1"
  account_id          = "311923415472"
  environment         = "prod"
  project_name        = "trii"
  repository          = "danielnmuner/trii"
  github_actions_role = "arn:aws:iam::311923415472:role/GitHubTerraformTriiRole"
  state_bucket_name   = "trii-terraform-state-311923415472-us-east-1"

  common_tags = {
    ManagedBy   = "terraform"
    Environment = local.environment
    Project     = local.project_name
    Repository  = local.repository
  }
}
