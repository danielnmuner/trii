output "function_name" {
  description = "Daily closing snapshots updater Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "Daily closing snapshots updater Lambda function ARN."
  value       = module.function.function_arn
}
