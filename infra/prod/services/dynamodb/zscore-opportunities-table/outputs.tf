output "name" {
  description = "Z-score opportunities table name."
  value       = module.table.name
}

output "arn" {
  description = "Z-score opportunities table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Z-score opportunities table GSI ARNs."
  value       = module.table.index_arns
}
