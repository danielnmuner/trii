data "aws_iam_policy_document" "inline" {
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
    sid    = "ReadHistoricStats"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.historic_stats_table_arn],
      var.historic_stats_index_arns,
    )
  }

  statement {
    sid    = "WriteMarketAiRecommendations"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
    ]
    resources = [var.market_ai_recommendations_table_arn]
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

  function_name = "${var.project_name}-${var.environment}-market-ai-recommendation-handler"
  description   = "Builds market recommendation context and stores the AI market view."
  source_dir    = "${path.module}/src"
  timeout       = 60
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE         = var.current_snapshots_table_name
    HISTORIC_STATS_TABLE            = var.historic_stats_table_name
    MARKET_AI_RECOMMENDATIONS_TABLE = var.market_ai_recommendations_table_name
    BEDROCK_MODEL_ID                = var.bedrock_model_id
    INVOKE_BEDROCK_MODEL            = "false"
  }

  tags = var.tags
}
