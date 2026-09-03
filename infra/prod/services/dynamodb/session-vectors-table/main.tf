module "table" {
  source = "../../../../modules/dynamodb/table"

  name      = "${var.project_name}-${var.environment}-session-vectors"
  hash_key  = "symbol"
  range_key = "record_type"

  attributes = [
    { name = "symbol", type = "S" },
    { name = "record_type", type = "S" },
  ]

  point_in_time_recovery_enabled = false
  ttl_enabled        = true
  ttl_attribute_name = "expires_at"

  tags = var.tags
}
