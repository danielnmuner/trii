output "api_endpoint" {
  description = "HTTP API invoke URL."
  value       = module.http_api.api_endpoint
}

output "api_id" {
  description = "HTTP API ID."
  value       = module.http_api.api_id
}
