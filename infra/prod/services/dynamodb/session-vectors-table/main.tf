module "table" {
  source = "../../../../modules/dynamodb/table"

  name      = "${var.project_name}-${var.environment}-session-vectors"
  hash_key  = "symbol"
  range_key = "record_type"

  attributes = [
    { name = "symbol", type = "S" },
    { name = "record_type", type = "S" },
  ]

  ttl_enabled        = true
  ttl_attribute_name = "expires_at"

  tags = var.tags
}
