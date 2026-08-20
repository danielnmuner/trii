output "name" {
  description = "Historic stats table name."
  value       = module.table.name
}

output "arn" {
  description = "Historic stats table ARN."
  value       = module.table.arn
}

output "index_arns" {
  description = "Historic stats table GSI ARNs."
  value       = module.table.index_arns
}
