module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-processed-stats-events"
  hash_key = "snapshot_checksum"

  attributes = [
    { name = "snapshot_checksum", type = "S" },
    { name = "captured_date", type = "S" },
    { name = "symbol_captured_at", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "captured-date-index"
      hash_key  = "captured_date"
      range_key = "symbol_captured_at"
    },
  ]

  tags = var.tags
}
