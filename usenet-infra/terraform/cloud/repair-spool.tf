variable "repair_spool_enabled" {
  description = "Provision the explicitly approved 300 GB incomplete/repair spool."
  type        = bool
  default     = false
}

resource "hcloud_volume" "repair_spool" {
  count             = var.repair_spool_enabled ? 1 : 0
  name              = "${var.name_prefix}-repair-spool"
  size              = 300
  location          = var.location
  delete_protection = true
  labels            = local.common_labels

  # Format only after matching the new device to the provider's volume ID.
  lifecycle {
    prevent_destroy = true
  }
}

resource "hcloud_volume_attachment" "repair_spool" {
  count     = var.repair_spool_enabled ? 1 : 0
  volume_id = hcloud_volume.repair_spool[0].id
  server_id = hcloud_server.acquisition.id
  automount = false
}

output "repair_spool" {
  description = "Pinned device identity for the approved spool deployment."
  value = var.repair_spool_enabled ? {
    volume_id    = hcloud_volume.repair_spool[0].id
    linux_device = hcloud_volume.repair_spool[0].linux_device
    size_gb      = hcloud_volume.repair_spool[0].size
  } : null
}
