module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-stock-orders"
  hash_key = "record_checksum"

  attributes = [
    { name = "record_checksum", type = "S" },
    { name = "symbol", type = "S" },
    { name = "ordered_at", type = "S" },
    { name = "ordered_month", type = "S" },
    { name = "ordered_at_symbol", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "symbol-ordered-at-index"
      hash_key  = "symbol"
      range_key = "ordered_at"
    },
    {
      name      = "ordered-month-index"
      hash_key  = "ordered_month"
      range_key = "ordered_at_symbol"
    },
  ]

  tags = var.tags
}
