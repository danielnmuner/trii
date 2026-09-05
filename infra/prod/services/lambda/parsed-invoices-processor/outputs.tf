output "function_name" {
  description = "Parsed invoices processor Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "Parsed invoices processor Lambda function ARN."
  value       = module.function.function_arn
}
