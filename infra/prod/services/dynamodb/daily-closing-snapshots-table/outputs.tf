output "name" {
  description = "Daily closing snapshots table name."
  value       = module.table.name
}

output "arn" {
  description = "Daily closing snapshots table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Daily closing snapshots table GSI ARNs."
  value       = module.table.index_arns
}
