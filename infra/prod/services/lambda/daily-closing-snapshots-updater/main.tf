data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = concat(
      [var.current_snapshots_table_arn],
      var.current_snapshots_index_arns,
    )
  }

  statement {
    sid    = "ReadWriteDailyClosingSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = concat(
      [var.daily_closing_snapshots_table_arn],
      var.daily_closing_snapshots_index_arns,
    )
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-daily-closing-snapshots-updater"
  description   = "Backfills and maintains per-symbol daily closing snapshots from current snapshots."
  source_dir    = "${path.module}/src"
  timeout       = 900
  memory_size   = 1024
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE       = var.current_snapshots_table_name
    DAILY_CLOSING_SNAPSHOTS_TABLE = var.daily_closing_snapshots_table_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.project_name}-${var.environment}-daily-closing-snapshots-updater"
  description         = "Runs the daily closing snapshots updater once per day after market close in Bogota."
  schedule_expression = var.schedule_expression

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.schedule.name
  target_id = "daily-closing-snapshots-updater"
  arn       = module.function.function_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridgeDailyClosingSnapshots"
  action        = "lambda:InvokeFunction"
  function_name = module.function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule.arn
}
