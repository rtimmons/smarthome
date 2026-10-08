# Dedicated settings-backup account; no canonical storage resources managed here.
variable "storage_box_id" { type = number }
variable "backup_password" {
  type      = string
  sensitive = true
}
resource "hcloud_storage_box_subaccount" "nas_backup" {
  storage_box_id = var.storage_box_id
  name           = "nas-settings-backup"
  home_directory = "catalog/.backups/nas-settings"
  password       = var.backup_password
  description    = "Encrypted NAS settings backups only; no canonical media access"
  access_settings = {
    reachable_externally = true
    readonly             = false
    samba_enabled        = false
    ssh_enabled          = true
    webdav_enabled       = false
  }
  labels = { service = "usenet-backup", managed-by = "terraform" }
  lifecycle { prevent_destroy = true }
}
output "account" {
  value = {
    server   = hcloud_storage_box_subaccount.nas_backup.server
    username = hcloud_storage_box_subaccount.nas_backup.username
    id       = hcloud_storage_box_subaccount.nas_backup.id
  }
}
