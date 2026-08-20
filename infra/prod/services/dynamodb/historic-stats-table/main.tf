module "table" {
  source = "../../../../modules/dynamodb/table"

  name      = "${var.project_name}-${var.environment}-historic-stats"
  hash_key  = "pk"
  range_key = "sk"

  attributes = [
    { name = "pk", type = "S" },
    { name = "sk", type = "S" },
    { name = "symbol_metric", type = "S" },
    { name = "last_source_captured_at", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "symbol-metric-captured-at-index"
      hash_key  = "symbol_metric"
      range_key = "last_source_captured_at"
    },
  ]

  tags = var.tags
}
