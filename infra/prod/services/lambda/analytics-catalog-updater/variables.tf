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

variable "analytics_catalog_table_name" {
  description = "Analytics catalog table name."
  type        = string
}

variable "analytics_catalog_table_arn" {
  description = "Analytics catalog table ARN."
  type        = string
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
