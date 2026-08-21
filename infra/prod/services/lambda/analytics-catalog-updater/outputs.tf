output "function_name" {
  description = "Analytics catalog updater Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "Analytics catalog updater Lambda function ARN."
  value       = module.function.function_arn
}
