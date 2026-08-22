module "http_api" {
  source = "../../../../modules/apigateway/http-api"

  name                 = "${var.project_name}-${var.environment}-http-api"
  lambda_function_name = var.api_handler_function_name
  lambda_invoke_arn    = var.api_handler_invoke_arn
  route_definitions = [
    {
      route_key          = "GET /health"
      authorization_type = "NONE"
    },
    {
      route_key          = "GET /analytics/catalog"
      authorization_type = "NONE"
    },
    {
      route_key          = "GET /analytics/daily-closing"
      authorization_type = "NONE"
    },
    {
      route_key          = "GET /analytics/historic-stats"
      authorization_type = "NONE"
    },
    {
      route_key          = "GET /analytics/snapshot"
      authorization_type = "NONE"
    },
    {
      route_key          = "GET /analytics/zscore-opportunities"
      authorization_type = "NONE"
    },
    {
      route_key          = "GET /snapshots"
      authorization_type = "NONE"
    },
    {
      route_key          = "GET /orders"
      authorization_type = "NONE"
    },
    {
      route_key          = "POST /snapshots"
      authorization_type = "NONE"
    },
    {
      route_key          = "POST /orders"
      authorization_type = "NONE"
    },
    {
      route_key          = "POST /invoices"
      authorization_type = "NONE"
    },
    {
      route_key          = "POST /documents"
      authorization_type = "NONE"
    },
  ]
  tags = var.tags
}
