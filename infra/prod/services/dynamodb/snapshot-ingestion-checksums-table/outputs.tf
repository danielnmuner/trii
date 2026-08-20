output "name" {
  description = "Snapshot ingestion checksums table name."
  value       = module.table.name
}

output "arn" {
  description = "Snapshot ingestion checksums table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Snapshot ingestion checksums table GSI ARNs."
  value       = module.table.index_arns
}
