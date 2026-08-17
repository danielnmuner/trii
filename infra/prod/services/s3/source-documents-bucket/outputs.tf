output "bucket_name" {
  description = "Source documents bucket name."
  value       = module.bucket.bucket_name
}

output "bucket_arn" {
  description = "Source documents bucket ARN."
  value       = module.bucket.bucket_arn
}
