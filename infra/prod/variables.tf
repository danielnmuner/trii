variable "api_gateway_shared_token" {
  description = "Shared token used by Streamlit to authenticate against the HTTP API."
  type        = string
  sensitive   = true
}
