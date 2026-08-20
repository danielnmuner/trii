output "name" {
  description = "Snapshot ingestion raw table name."
  value       = module.table.name
}

output "arn" {
  description = "Snapshot ingestion raw table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Snapshot ingestion raw table GSI ARNs."
  value       = module.table.index_arns
}
