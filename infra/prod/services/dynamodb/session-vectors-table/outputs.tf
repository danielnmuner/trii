output "name" {
  description = "Session vectors table name."
  value       = module.table.name
}

output "arn" {
  description = "Session vectors table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Session vectors table GSI ARNs."
  value       = module.table.index_arns
}
