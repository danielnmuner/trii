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
