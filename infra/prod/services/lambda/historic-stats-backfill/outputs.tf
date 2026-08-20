output "function_name" {
  description = "Historic stats backfill Lambda function name."
  value       = module.function.function_name
}

output "function_arn" {
  description = "Historic stats backfill Lambda function ARN."
  value       = module.function.function_arn
}
