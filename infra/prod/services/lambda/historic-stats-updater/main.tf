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
    sid    = "ReadCurrentSnapshotsTable"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
    ]
    resources = [var.current_snapshots_table_arn]
  }

  statement {
    sid    = "ReadWriteHistoricStats"
    effect = "Allow"
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:TransactWriteItems",
    ]
    resources = concat(
      [var.historic_stats_table_arn],
      var.historic_stats_index_arns,
    )
  }

}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-historic-stats-updater"
  description   = "Consumes current snapshots stream records and incrementally updates official historic stats."
  source_dir    = "${path.module}/src"
  timeout       = 60
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE     = var.current_snapshots_table_name
    HISTORIC_STATS_TABLE        = var.historic_stats_table_name
    ENABLED_STATISTICAL_METRICS = join(",", var.enabled_statistical_metrics)
  }

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "current_snapshots_stream" {
  event_source_arn  = var.current_snapshots_stream_arn
  function_name     = module.function.function_arn
  starting_position = "LATEST"
  batch_size        = 10
}
