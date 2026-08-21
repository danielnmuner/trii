variable "project_name" {
  description = "Project name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name."
  type        = string
}

variable "current_snapshots_stream_arn" {
  description = "Current snapshots DynamoDB stream ARN."
  type        = string
}

variable "current_snapshots_table_name" {
  description = "Current snapshots table name."
  type        = string
}

variable "current_snapshots_table_arn" {
  description = "Current snapshots table ARN."
  type        = string
}

variable "historic_stats_table_name" {
  description = "Historic stats table name."
  type        = string
}

variable "historic_stats_table_arn" {
  description = "Historic stats table ARN."
  type        = string
}

variable "historic_stats_index_arns" {
  description = "Historic stats table index ARNs."
  type        = list(string)
}

variable "processed_stats_events_table_name" {
  description = "Processed stats events table name."
  type        = string
}

variable "processed_stats_events_table_arn" {
  description = "Processed stats events table ARN."
  type        = string
}

variable "processed_stats_events_index_arns" {
  description = "Processed stats events table index ARNs."
  type        = list(string)
}

variable "stock_orders_table_name" {
  description = "Stock orders table name."
  type        = string
}

variable "stock_orders_table_arn" {
  description = "Stock orders table ARN."
  type        = string
}

variable "stock_orders_index_arns" {
  description = "Stock orders table index ARNs."
  type        = list(string)
}

variable "zscore_opportunities_table_name" {
  description = "Z-score opportunities table name."
  type        = string
}

variable "zscore_opportunities_table_arn" {
  description = "Z-score opportunities table ARN."
  type        = string
}

variable "zscore_opportunities_index_arns" {
  description = "Z-score opportunities table index ARNs."
  type        = list(string)
}

variable "market_ai_recommendation_handler_function_name" {
  description = "Market AI recommendation handler Lambda function name."
  type        = string
}

variable "market_ai_recommendation_handler_function_arn" {
  description = "Market AI recommendation handler Lambda function ARN."
  type        = string
}

variable "enabled_statistical_metrics" {
  description = "Statistical metrics that the live updater is allowed to persist."
  type        = list(string)
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
