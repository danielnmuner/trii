output "name" {
  description = "Analytics catalog table name."
  value       = module.table.name
}

output "arn" {
  description = "Analytics catalog table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Analytics catalog table GSI ARNs."
  value       = module.table.index_arns
}
