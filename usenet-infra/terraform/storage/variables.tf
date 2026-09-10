variable "name_prefix" {
  description = "Prefix used for Storage Box resource names."
  type        = string
  default     = "usenet"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.name_prefix))
    error_message = "name_prefix must contain lowercase letters, digits, and hyphens, and must not start or end with a hyphen."
  }
}

variable "environment" {
  description = "Environment label applied to resources."
  type        = string
  default     = "production"
}

variable "location" {
  description = "Storage Box location. Current BX tiers are offered in FSN1 and HEL1."
  type        = string
  default     = "hel1"

  validation {
    condition     = contains(["fsn1", "hel1"], lower(var.location))
    error_message = "Storage Box location must be fsn1 or hel1."
  }
}

variable "storage_box_type" {
  description = "Storage Box capacity tier. Start at BX11 and increase this value for an in-place upgrade."
  type        = string
  default     = "bx11"

  validation {
    condition     = contains(["bx11", "bx21", "bx31", "bx41"], lower(var.storage_box_type))
    error_message = "storage_box_type must be bx11, bx21, bx31, or bx41."
  }
}

variable "storage_box_name" {
  description = "Unique name for the canonical Storage Box."
  type        = string
  default     = "usenet-catalog"
}

variable "storage_box_password" {
  description = "Strong, unique main-account password. This value is stored in Terraform state."
  type        = string
  sensitive   = true
}

variable "storage_box_ssh_public_keys" {
  description = "OpenSSH public keys injected when the Storage Box is first created. Set these before the first apply; the API cannot update them later."
  type        = set(string)

  validation {
    condition     = length(var.storage_box_ssh_public_keys) > 0
    error_message = "Provide at least one Storage Box main-account SSH public key before creation."
  }
}

variable "qnap_subaccount_name" {
  description = "Name for the QNAP read-only Storage Box subaccount."
  type        = string
  default     = "qnap-reader"
}

variable "qnap_home_directory" {
  description = "Catalog directory exposed as the QNAP subaccount root. It must not begin with a slash."
  type        = string
  default     = "catalog"

  validation {
    condition = (
      !startswith(var.qnap_home_directory, "/") &&
      can(regex("^[A-Za-z0-9._/-]+$", var.qnap_home_directory))
    )
    error_message = "qnap_home_directory must be a relative Storage Box path using letters, digits, dots, slashes, underscores, or hyphens."
  }
}

variable "qnap_subaccount_password" {
  description = "Strong, unique fallback password for the QNAP subaccount. This value is stored in Terraform state; use SSH-key authentication operationally."
  type        = string
  sensitive   = true
}

variable "additional_labels" {
  description = "Additional labels merged onto all supported storage resources."
  type        = map(string)
  default     = {}
}
