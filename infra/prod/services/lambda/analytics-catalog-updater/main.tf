data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshotsStream"
    effect = "Allow"
    actions = [
      "dynamodb:DescribeStream",
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:ListStreams",
    ]
    resources = [var.current_snapshots_stream_arn]
  }

  statement {
    sid    = "ReadWriteAnalyticsCatalog"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
    ]
    resources = [var.analytics_catalog_table_arn]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-analytics-catalog-updater"
  description   = "Maintains a materialized analytics catalog from current snapshots stream inserts."
  source_dir    = "${path.module}/src"
  timeout       = 60
  memory_size   = 256
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    ANALYTICS_CATALOG_TABLE = var.analytics_catalog_table_name
  }

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "current_snapshots_stream" {
  event_source_arn  = var.current_snapshots_stream_arn
  function_name     = module.function.function_arn
  starting_position = "LATEST"
  batch_size        = 100
}
