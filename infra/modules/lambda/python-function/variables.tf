variable "function_name" {
  description = "Lambda function name."
  type        = string
}

variable "description" {
  description = "Lambda description."
  type        = string
  default     = null
}

variable "handler" {
  description = "Lambda handler."
  type        = string
  default     = "handler.handler"
}

variable "runtime" {
  description = "Lambda runtime."
  type        = string
  default     = "python3.12"
}

variable "source_dir" {
  description = "Directory that will be zipped and deployed."
  type        = string
}

variable "memory_size" {
  description = "Lambda memory size."
  type        = number
  default     = 256
}

variable "timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 30
}

variable "architectures" {
  description = "Lambda CPU architectures."
  type        = list(string)
  default     = ["x86_64"]
}

variable "environment_variables" {
  description = "Lambda environment variables."
  type        = map(string)
  default     = {}
}

variable "policy_json" {
  description = "Optional inline IAM policy JSON."
  type        = string
  default     = null
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
