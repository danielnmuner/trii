output "function_name" {
  description = "API handler Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "API handler Lambda function ARN."
  value       = module.function.function_arn
}

output "invoke_arn" {
  description = "API handler Lambda invoke ARN."
  value       = module.function.invoke_arn
}
