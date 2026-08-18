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

variable "stock_orders_table_name" {
  description = "Stock orders table name."
  type        = string
}

variable "stock_orders_table_arn" {
  description = "Stock orders table ARN."
  type        = string
}

variable "parsed_invoices_table_name" {
  description = "Parsed invoices table name."
  type        = string
}

variable "parsed_invoices_table_arn" {
  description = "Parsed invoices table ARN."
  type        = string
}

variable "source_documents_bucket_name" {
  description = "Source documents bucket name."
  type        = string
}

variable "source_documents_bucket_arn" {
  description = "Source documents bucket ARN."
  type        = string
}

variable "ai_handler_function_name" {
  description = "AI handler Lambda function name."
  type        = string
}

variable "ai_handler_function_arn" {
  description = "AI handler Lambda function ARN."
  type        = string
}

variable "api_gateway_shared_token" {
  description = "Shared token required by API Gateway clients."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
