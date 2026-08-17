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

variable "parsed_invoices_table_name" {
  description = "Parsed invoices table name."
  type        = string
}

variable "parsed_invoices_table_arn" {
  description = "Parsed invoices table ARN."
  type        = string
}

variable "parsed_invoices_index_arns" {
  description = "Parsed invoices table index ARNs."
  type        = list(string)
}

variable "source_documents_bucket_name" {
  description = "Source documents bucket name."
  type        = string
}

variable "source_documents_bucket_arn" {
  description = "Source documents bucket ARN."
  type        = string
}

variable "bedrock_model_id" {
  description = "Bedrock model identifier."
  type        = string
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
