output "name" {
  description = "Market AI recommendations table name."
  value       = module.table.name
}

output "arn" {
  description = "Market AI recommendations table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Market AI recommendations table GSI ARNs."
  value       = module.table.index_arns
}
