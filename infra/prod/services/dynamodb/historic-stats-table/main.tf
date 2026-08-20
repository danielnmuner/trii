module "table" {
  source = "../../../../modules/dynamodb/table"

  name      = "${var.project_name}-${var.environment}-historic-stats"
  hash_key  = "pk"
  range_key = "sk"

  attributes = [
    { name = "pk", type = "S" },
    { name = "sk", type = "S" },
    { name = "symbol_metric", type = "S" },
    { name = "bucket_time", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "symbol-metric-bucket-time-index"
      hash_key  = "symbol_metric"
      range_key = "bucket_time"
    },
  ]

  tags = var.tags
}
