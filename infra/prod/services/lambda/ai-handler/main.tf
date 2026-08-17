data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.current_snapshots_table_arn],
      var.current_snapshots_index_arns,
    )
  }

  statement {
    sid    = "ReadStockOrders"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.stock_orders_table_arn],
      var.stock_orders_index_arns,
    )
  }

  statement {
    sid    = "ReadParsedInvoices"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.parsed_invoices_table_arn],
      var.parsed_invoices_index_arns,
    )
  }

  statement {
    sid    = "ReadSourceDocuments"
    effect = "Allow"
    actions = [
      "s3:GetObject",
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
    sid    = "InvokeBedrockModels"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:Converse",
      "bedrock:ConverseStream",
    ]
    resources = ["*"]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-ai-handler"
  description   = "Reads optional context and orchestrates Bedrock calls."
  source_dir    = "${path.module}/src"
  timeout       = 60
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE = var.current_snapshots_table_name
    STOCK_ORDERS_TABLE      = var.stock_orders_table_name
    PARSED_INVOICES_TABLE   = var.parsed_invoices_table_name
    SOURCE_DOCUMENTS_BUCKET = var.source_documents_bucket_name
    BEDROCK_MODEL_ID        = var.bedrock_model_id
  }

  tags = var.tags
}
