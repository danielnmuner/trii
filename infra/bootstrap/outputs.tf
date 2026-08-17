output "github_actions_role" {
  description = "Role assumed by GitHub Actions for Terraform."
  value       = local.github_actions_role
}

output "state_bucket_name" {
  description = "Terraform backend bucket name."
  value       = module.terraform_state_bucket.bucket_name
}
