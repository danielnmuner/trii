data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:Query",
    ]
    resources = [
      var.current_snapshots_table_arn,
      "${var.current_snapshots_table_arn}/index/*",
    ]
  }

  statement {
    sid    = "WriteCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [var.current_snapshots_table_arn]
  }

  statement {
    sid    = "WriteStockOrders"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [var.stock_orders_table_arn]
  }

  statement {
    sid    = "WriteParsedInvoices"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [var.parsed_invoices_table_arn]
  }

  statement {
    sid    = "WriteSourceDocuments"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${var.source_documents_bucket_arn}/*"]
  }

  statement {
    sid       = "ListSourceDocumentsBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.source_documents_bucket_arn]
  }

  statement {
    sid     = "InvokeAiHandler"
    effect  = "Allow"
    actions = ["lambda:InvokeFunction"]
    resources = [
      var.ai_handler_function_arn,
      "${var.ai_handler_function_arn}:*",
    ]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-api-handler"
  description   = "Receives HTTP API requests and persists operational records."
  source_dir    = "${path.module}/src"
  timeout       = 30
  memory_size   = 256
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE = var.current_snapshots_table_name
    STOCK_ORDERS_TABLE      = var.stock_orders_table_name
    PARSED_INVOICES_TABLE   = var.parsed_invoices_table_name
    SOURCE_DOCUMENTS_BUCKET = var.source_documents_bucket_name
    AI_HANDLER_FUNCTION     = var.ai_handler_function_name
    API_SHARED_TOKEN        = var.api_gateway_shared_token
  }

  tags = var.tags
}
