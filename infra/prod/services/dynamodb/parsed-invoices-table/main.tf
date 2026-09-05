module "table" {
  source = "../../../../modules/dynamodb/table"

  name     = "${var.project_name}-${var.environment}-parsed-invoices"
  hash_key = "invoice_uuid"

  attributes = [
    { name = "invoice_uuid", type = "S" },
    { name = "user_order_reference_id", type = "S" },
    { name = "issued_at", type = "S" },
    { name = "user_issued_month", type = "S" },
    { name = "issued_at_invoice_number", type = "S" },
    { name = "source_xml_checksum", type = "S" },
  ]

  global_secondary_indexes = [
    {
      name      = "user-order-reference-issued-at-index"
      hash_key  = "user_order_reference_id"
      range_key = "issued_at"
    },
    {
      name      = "user-issued-month-index"
      hash_key  = "user_issued_month"
      range_key = "issued_at_invoice_number"
    },
    {
      name     = "source-xml-checksum-index"
      hash_key = "source_xml_checksum"
    },
  ]

  tags = var.tags
}
