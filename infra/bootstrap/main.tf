module "terraform_state_bucket" {
  source = "../modules/terraform-state-bucket"

  bucket_name = local.state_bucket_name
  common_tags = local.common_tags
}
