module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-stock-orders"
  hash_key = "record_checksum"

  attributes = [
    { name = "record_checksum", type = "S" },
    { name = "user_symbol", type = "S" },
    { name = "created_at", type = "S" },
    { name = "user_created_month", type = "S" },
    { name = "created_at_symbol", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "user-symbol-created-at-index"
      hash_key  = "user_symbol"
      range_key = "created_at"
    },
    {
      name      = "user-created-month-index"
      hash_key  = "user_created_month"
      range_key = "created_at_symbol"
    },
  ]

  tags = var.tags
}
