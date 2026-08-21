module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-zscore-opportunities"
  hash_key = "snapshot_checksum"

  attributes = [
    { name = "snapshot_checksum", type = "S" },
    { name = "symbol", type = "S" },
    { name = "captured_at", type = "S" },
    { name = "trading_date", type = "S" },
    { name = "symbol_captured_at", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "symbol-created-at-index"
      hash_key  = "symbol"
      range_key = "captured_at"
    },
    {
      name      = "trading-date-index"
      hash_key  = "trading_date"
      range_key = "symbol_captured_at"
    },
  ]

  tags = var.tags
}
