output "name" {
  description = "Stock orders table name."
  value       = module.table.name
}

output "arn" {
  description = "Stock orders table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Stock orders table GSI ARNs."
  value       = module.table.index_arns
}
