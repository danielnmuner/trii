module "table" {
  source = "../../../../modules/dynamodb/table"

  name      = "${var.project_name}-${var.environment}-daily-closing-snapshots"
  hash_key  = "symbol"
  range_key = "trading_date"

  attributes = [
    { name = "symbol", type = "S" },
    { name = "trading_date", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "trading-date-index"
      hash_key  = "trading_date"
      range_key = "symbol"
    },
  ]

  tags = var.tags
}
