module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-stock-orders"
  hash_key = "record_checksum"

  attributes = [
    { name = "record_checksum", type = "S" },
    { name = "symbol", type = "S" },
    { name = "created_at", type = "S" },
    { name = "created_month", type = "S" },
    { name = "created_at_symbol", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "symbol-created-at-index"
      hash_key  = "symbol"
      range_key = "created_at"
    },
    {
      name      = "created-month-index"
      hash_key  = "created_month"
      range_key = "created_at_symbol"
    },
  ]

  tags = var.tags
}
