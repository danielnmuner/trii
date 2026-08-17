output "api_id" {
  description = "HTTP API ID."
  value       = aws_apigatewayv2_api.this.id
}

output "api_endpoint" {
  description = "HTTP API invoke endpoint."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "execution_arn" {
  description = "HTTP API execution ARN."
  value       = aws_apigatewayv2_api.this.execution_arn
}
