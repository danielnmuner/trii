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

variable "daily_closing_snapshots_table_name" {
  description = "Daily closing snapshots table name."
  type        = string
}

variable "daily_closing_snapshots_table_arn" {
  description = "Daily closing snapshots table ARN."
  type        = string
}

variable "daily_closing_snapshots_index_arns" {
  description = "Daily closing snapshots table index ARNs."
  type        = list(string)
}

variable "schedule_expression" {
  description = "EventBridge schedule expression for the daily closing updater."
  type        = string
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
