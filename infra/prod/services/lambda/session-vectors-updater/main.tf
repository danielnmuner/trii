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
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.current_snapshots_table_arn],
      var.current_snapshots_index_arns,
    )
  }

  statement {
    sid    = "ReadAnalyticsCatalog"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
    ]
    resources = [var.analytics_catalog_table_arn]
  }

  statement {
    sid    = "ReadWriteSessionVectors"
    effect = "Allow"
    actions = [
      "dynamodb:BatchWriteItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
    ]
    resources = [var.session_vectors_table_arn]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-session-vectors-updater"
  description   = "Maintains session vector manifests and segments from current snapshots, with stream-triggered updates and manual latest-day rebuild support."
  source_dir    = "${path.module}/src"
  timeout       = 180
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE = var.current_snapshots_table_name
    ANALYTICS_CATALOG_TABLE = var.analytics_catalog_table_name
    SESSION_VECTORS_TABLE   = var.session_vectors_table_name
  }

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "current_snapshots_stream" {
  event_source_arn  = var.current_snapshots_stream_arn
  function_name     = module.function.function_arn
  starting_position = "LATEST"
  batch_size        = 100
}
