data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadWriteHistoricStats"
    effect = "Allow"
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:DeleteItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = concat(
      [var.historic_stats_table_arn],
      var.historic_stats_index_arns,
    )
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-historic-stats-summary-migrator"
  description   = "Temporarily materializes stats_summary records from legacy historic stat items and can validate or clean them up."
  source_dir    = "${path.module}/src"
  timeout       = 180
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    HISTORIC_STATS_TABLE = var.historic_stats_table_name
  }

  tags = var.tags
}
