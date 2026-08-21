module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-analytics-catalog"
  hash_key = "pk"

  attributes = [
    { name = "pk", type = "S" },
  ]

  tags = var.tags
}
