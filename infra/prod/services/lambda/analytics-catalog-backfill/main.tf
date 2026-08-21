data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:Query",
    ]
    resources = concat(
      [var.current_snapshots_table_arn],
      var.current_snapshots_index_arns,
    )
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

  function_name = "${var.project_name}-${var.environment}-analytics-catalog-backfill"
  description   = "Manual backfill job that rebuilds the analytics catalog materialized view."
  source_dir    = "${path.module}/src"
  timeout       = 900
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE = var.current_snapshots_table_name
    ANALYTICS_CATALOG_TABLE = var.analytics_catalog_table_name
  }

  tags = var.tags
}
