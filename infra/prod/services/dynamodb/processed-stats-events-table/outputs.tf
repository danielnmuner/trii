output "name" {
  description = "Processed stats events table name."
  value       = module.table.name
}

output "arn" {
  description = "Processed stats events table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Processed stats events table GSI ARNs."
  value       = module.table.index_arns
}
