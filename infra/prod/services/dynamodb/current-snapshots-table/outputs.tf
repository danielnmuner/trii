output "name" {
  description = "Current snapshots table name."
  value       = module.table.name
}

output "arn" {
  description = "Current snapshots table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Current snapshots table GSI ARNs."
  value       = module.table.index_arns
}

output "stream_arn" {
  description = "Current snapshots table stream ARN."
  value       = module.table.stream_arn
}
