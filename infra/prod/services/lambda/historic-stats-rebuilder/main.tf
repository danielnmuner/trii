data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:Scan",
    ]
    resources = [var.current_snapshots_table_arn]
  }

  statement {
    sid    = "WriteHistoricStats"
    effect = "Allow"
    actions = [
      "dynamodb:BatchWriteItem",
      "dynamodb:PutItem",
    ]
    resources = [var.historic_stats_table_arn]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-historic-stats-rebuilder"
  description   = "Rebuilds official historic stats from the raw snapshots table."
  source_dir    = "${path.module}/src"
  timeout       = 300
  memory_size   = 1024
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE = var.current_snapshots_table_name
    HISTORIC_STATS_TABLE    = var.historic_stats_table_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "rebuild_schedule" {
  name                = "${var.project_name}-${var.environment}-historic-stats-rebuild-12h"
  description         = "Rebuild historic stats every 12 hours from the raw current snapshots table."
  schedule_expression = "rate(12 hours)"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "rebuild_lambda" {
  rule      = aws_cloudwatch_event_rule.rebuild_schedule.name
  target_id = "historic-stats-rebuilder"
  arn       = module.function.function_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridgeHistoricStatsRebuild"
  action        = "lambda:InvokeFunction"
  function_name = module.function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.rebuild_schedule.arn
}
