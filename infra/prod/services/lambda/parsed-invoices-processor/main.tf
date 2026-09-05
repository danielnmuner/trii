data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadSourceDocumentsBucket"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.source_documents_bucket_arn,
      "${var.source_documents_bucket_arn}/*",
    ]
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
    sid    = "WriteParsedInvoices"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
    ]
    resources = [var.parsed_invoices_table_arn]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-parsed-invoices-processor"
  description   = "Parses uploaded invoice XML files from S3 and persists idempotent invoice records."
  source_dir    = "${path.module}/src"
  timeout       = 60
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    SOURCE_DOCUMENTS_BUCKET = var.source_documents_bucket_name
    PARSED_INVOICES_TABLE   = var.parsed_invoices_table_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "source_documents_object_created" {
  name        = "${var.project_name}-${var.environment}-parsed-invoices-processor"
  description = "Runs the parsed invoices processor for new source document uploads."
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.source_documents_bucket_name]
      }
      object = {
        key = [
          {
            prefix = "invoices/"
          }
        ]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.source_documents_object_created.name
  target_id = "parsed-invoices-processor"
  arn       = module.function.function_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridgeParsedInvoicesProcessor"
  action        = "lambda:InvokeFunction"
  function_name = module.function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.source_documents_object_created.arn
}
