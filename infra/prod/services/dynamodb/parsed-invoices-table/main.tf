module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-parsed-invoices"
  hash_key = "invoice_uuid"

  attributes = [
    { name = "invoice_uuid", type = "S" },
    { name = "order_reference_id", type = "S" },
    { name = "issued_at", type = "S" },
    { name = "issued_month", type = "S" },
    { name = "issued_at_invoice_number", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "order-reference-issued-at-index"
      hash_key  = "order_reference_id"
      range_key = "issued_at"
    },
    {
      name      = "issued-month-index"
      hash_key  = "issued_month"
      range_key = "issued_at_invoice_number"
    },
  ]

  tags = var.tags
}
