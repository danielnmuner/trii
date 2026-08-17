variable "project_name" {
  description = "Project name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name."
  type        = string
}

variable "api_handler_function_name" {
  description = "API handler Lambda function name."
  type        = string
}

variable "api_handler_invoke_arn" {
  description = "API handler Lambda invoke ARN."
  type        = string
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
