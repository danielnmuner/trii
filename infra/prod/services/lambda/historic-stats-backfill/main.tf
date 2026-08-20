data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [var.current_snapshots_table_arn]
  }

  statement {
    sid    = "WriteHistoricStats"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
    ]
    resources = [var.historic_stats_table_arn]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-historic-stats-backfill"
  description   = "Manual backfill job for historic stats metrics derived from current snapshots."
  source_dir    = "${path.module}/src"
  timeout       = 900
  memory_size   = 1024
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE     = var.current_snapshots_table_name
    HISTORIC_STATS_TABLE        = var.historic_stats_table_name
    ENABLED_STATISTICAL_METRICS = join(",", var.enabled_statistical_metrics)
  }

  tags = var.tags
}
