output "aws_account_id" {
  description = "AWS account where Terraform is executing."
  value       = data.aws_caller_identity.current.account_id
}

output "state_bucket_name" {
  description = "Terraform backend bucket used by the prod root module."
  value       = local.state_bucket_name
}
