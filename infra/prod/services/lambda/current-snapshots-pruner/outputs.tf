output "function_name" {
  description = "Current snapshots pruner Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "Current snapshots pruner Lambda function ARN."
  value       = module.function.function_arn
}
