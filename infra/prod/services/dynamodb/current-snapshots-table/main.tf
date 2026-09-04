module "table" {
  source = "../../../../modules/dynamodb/table"

  name      = "${var.project_name}-${var.environment}-current-snapshots"
  hash_key  = "symbol"
  range_key = "captured_at"

  attributes = [
    { name = "symbol", type = "S" },
    { name = "captured_at", type = "S" },
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

  stream_enabled     = true
  stream_view_type   = "NEW_IMAGE"
  point_in_time_recovery_enabled = false

  tags = var.tags
}
