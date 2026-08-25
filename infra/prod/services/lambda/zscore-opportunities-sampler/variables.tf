variable "project_name" {
  description = "Project name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name."
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

variable "current_snapshots_index_arns" {
  description = "Current snapshots table index ARNs."
  type        = list(string)
}

variable "historic_stats_table_name" {
  description = "Historic stats table name."
  type        = string
}

variable "historic_stats_table_arn" {
  description = "Historic stats table ARN."
  type        = string
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

variable "schedule_expression" {
  description = "EventBridge schedule expression for the z-score opportunities sampler."
  type        = string
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
