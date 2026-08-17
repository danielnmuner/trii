output "name" {
  description = "Parsed invoices table name."
  value       = module.table.name
}

output "arn" {
  description = "Parsed invoices table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Parsed invoices table GSI ARNs."
  value       = module.table.index_arns
}
