module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-market-ai-recommendations"
  hash_key = "trigger_signature"

  attributes = [
    { name = "trigger_signature", type = "S" },
    { name = "symbol", type = "S" },
    { name = "created_at", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "symbol-created-at-index"
      hash_key  = "symbol"
      range_key = "created_at"
    },
  ]

  tags = var.tags
}
