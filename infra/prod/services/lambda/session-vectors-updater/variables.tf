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

variable "session_vectors_table_name" {
  description = "Session vectors table name."
  type        = string
}

variable "session_vectors_table_arn" {
  description = "Session vectors table ARN."
  type        = string
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
