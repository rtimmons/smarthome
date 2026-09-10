variable "name_prefix" {
  description = "Prefix used for Hetzner Cloud resource names."
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
  description = "Hetzner location for the server and its Primary IPs. HEL1 can colocate with a Storage Box; choose a location where the selected server type is available."
  type        = string
  default     = "hel1"
}

variable "server_name" {
  description = "DNS-compatible name for the acquisition server."
  type        = string
  default     = "usenet-acquisition"
}

variable "server_type" {
  description = "Hetzner server type. CX43 is the low-cost 8 shared-vCPU, 16 GB RAM, 160 GB NVMe default; availability is capacity-dependent."
  type        = string
  default     = "cx43"
}

variable "image_name" {
  description = "Hetzner Ubuntu system image name. The data source below explicitly selects its x86 build."
  type        = string
  default     = "ubuntu-26.04"
}

variable "admin_ssh_public_key" {
  description = "OpenSSH-format public key installed on the server. Public keys are not secret."
  type        = string

  validation {
    condition     = can(regex("^(ssh-ed25519|ecdsa-sha2-nistp256|sk-ssh-ed25519@openssh.com|ssh-rsa) ", trimspace(var.admin_ssh_public_key)))
    error_message = "admin_ssh_public_key must be an OpenSSH-format public key."
  }
}

variable "admin_ssh_cidrs" {
  description = "IPv4 and/or IPv6 CIDRs allowed to reach TCP/22. Keep this to trusted /32 or /128 addresses where practical."
  type        = list(string)

  validation {
    condition = (
      length(var.admin_ssh_cidrs) > 0 &&
      alltrue([for cidr in var.admin_ssh_cidrs : can(cidrhost(cidr, 0))])
    )
    error_message = "admin_ssh_cidrs must contain at least one valid IPv4 or IPv6 CIDR."
  }
}

variable "additional_labels" {
  description = "Additional labels merged onto all supported cloud resources."
  type        = map(string)
  default     = {}
}
