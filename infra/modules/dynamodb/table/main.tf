locals {
  global_secondary_indexes = [
    for gsi in var.global_secondary_indexes : merge(gsi, {
      key_schema = concat(
        [
          {
            attribute_name = gsi.hash_key
            key_type       = "HASH"
          },
        ],
        try(gsi.range_key, null) == null ? [] : [
          {
            attribute_name = gsi.range_key
            key_type       = "RANGE"
          },
        ]
      )
    })
  ]
}

resource "aws_dynamodb_table" "this" {
  name             = var.name
  billing_mode     = var.billing_mode
  hash_key         = var.hash_key
  range_key        = var.range_key
  stream_enabled   = var.stream_enabled
  stream_view_type = var.stream_enabled ? var.stream_view_type : null

  dynamic "attribute" {
    for_each = var.attributes

    content {
      name = attribute.value.name
      type = attribute.value.type
    }
  }

  dynamic "global_secondary_index" {
    for_each = local.global_secondary_indexes

    content {
      name            = global_secondary_index.value.name
      projection_type = try(global_secondary_index.value.projection_type, "ALL")

      dynamic "key_schema" {
        for_each = global_secondary_index.value.key_schema

        content {
          attribute_name = key_schema.value.attribute_name
          key_type       = key_schema.value.key_type
        }
      }
    }
  }

  point_in_time_recovery {
    enabled = var.point_in_time_recovery_enabled
  }

  dynamic "ttl" {
    for_each = var.ttl_enabled ? [1] : []

    content {
      attribute_name = var.ttl_attribute_name
      enabled        = true
    }
  }

  tags = var.tags
}
