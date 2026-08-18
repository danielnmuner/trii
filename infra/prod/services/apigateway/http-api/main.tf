module "http_api" {
  source = "../../../../modules/apigateway/http-api"

  name                 = "${var.project_name}-${var.environment}-http-api"
  lambda_function_name = var.api_handler_function_name
  lambda_invoke_arn    = var.api_handler_invoke_arn
  route_keys = toset([
    "GET /health",
    "GET /snapshots",
    "POST /snapshots",
    "POST /orders",
    "POST /invoices",
    "POST /documents",
    "POST /ai/query",
  ])
  tags = var.tags
}
