output "function_name" {
  description = "Historic stats updater Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "Historic stats updater Lambda function ARN."
  value       = module.function.function_arn
}
