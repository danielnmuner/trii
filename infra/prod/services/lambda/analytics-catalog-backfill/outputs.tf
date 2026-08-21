output "function_name" {
  description = "Analytics catalog backfill Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "Analytics catalog backfill Lambda function ARN."
  value       = module.function.function_arn
}
