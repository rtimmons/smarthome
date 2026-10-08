# Independent disposable resources. Never import production state into this root.
variable "admin_ssh_key_id" {
  type        = number
  description = "Existing cloud administrator public key resource ID."
}
variable "admin_ssh_cidrs" {
  type        = list(string)
  description = "Existing trusted operator source CIDRs; SSH is the only inbound service."
  validation {
    condition     = length(var.admin_ssh_cidrs) > 0 && alltrue([for c in var.admin_ssh_cidrs : can(cidrhost(c, 0)) && !endswith(c, "/0")])
    error_message = "Provide trusted source CIDRs; global SSH ingress is forbidden."
  }
}
variable "bootstrap_file" {
  type        = string
  description = "Private cloud-init document with a pre-pinned disposable SSH host identity."
}
locals {
  name   = "codex-recovery-drill-20261008"
  labels = { purpose = "disposable-recovery-drill", managed-by = "terraform" }
}
resource "hcloud_firewall" "drill" {
  name   = local.name
  labels = local.labels
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.admin_ssh_cidrs
  }
}
resource "hcloud_server" "drill" {
  name         = local.name
  server_type  = "cx43"
  image        = "ubuntu-26.04"
  location     = "hel1"
  ssh_keys     = [var.admin_ssh_key_id]
  user_data    = sensitive(file(var.bootstrap_file))
  firewall_ids = [hcloud_firewall.drill.id]
  labels       = local.labels
  public_net {
    ipv4_enabled = true
    ipv6_enabled = false
  }
}
resource "hcloud_volume" "drill" {
  name     = local.name
  size     = 300
  location = "hel1"
  labels   = local.labels
}
resource "hcloud_volume_attachment" "drill" {
  volume_id = hcloud_volume.drill.id
  server_id = hcloud_server.drill.id
  automount = false
}
output "drill" {
  value = {
    server_id = hcloud_server.drill.id
    ipv4      = hcloud_server.drill.ipv4_address
    volume_id = hcloud_volume.drill.id
    device    = hcloud_volume.drill.linux_device
  }
}
