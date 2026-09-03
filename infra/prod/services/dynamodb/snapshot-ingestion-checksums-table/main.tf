module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-snapshot-ingestion-checksums"
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

  point_in_time_recovery_enabled = false
  ttl_enabled        = true
  ttl_attribute_name = "expires_at"

  tags = var.tags
}
