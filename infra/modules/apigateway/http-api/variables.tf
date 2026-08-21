variable "name" {
  description = "HTTP API name."
  type        = string
}

variable "stage_name" {
  description = "API stage name."
  type        = string
  default     = "$default"
}

variable "lambda_function_name" {
  description = "Lambda function name used by API Gateway."
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Lambda invoke ARN used by API Gateway integration."
  type        = string
}

variable "route_definitions" {
  description = "HTTP API routes and their authorization modes."
  type = list(object({
    route_key          = string
    authorization_type = optional(string, "NONE")
  }))
}

variable "cors_allow_origins" {
  description = "Allowed CORS origins."
  type        = list(string)
  default     = ["*"]
}

variable "cors_allow_headers" {
  description = "Allowed CORS headers."
  type        = list(string)
  default     = ["content-type", "authorization", "x-api-token"]
}

variable "cors_allow_methods" {
  description = "Allowed CORS methods."
  type        = list(string)
  default     = ["GET", "POST", "OPTIONS"]
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
