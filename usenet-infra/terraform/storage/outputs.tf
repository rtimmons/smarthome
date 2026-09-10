output "storage_box_id" {
  description = "Canonical Storage Box ID."
  value       = hcloud_storage_box.catalog.id
}

output "storage_box_server" {
  description = "Stable FQDN for main-account access from the Hetzner VM."
  value       = hcloud_storage_box.catalog.server
}

output "storage_box_username" {
  description = "Main-account username used only by the cloud ingestion path."
  value       = hcloud_storage_box.catalog.username
}

output "qnap_server" {
  description = "FQDN for the read-only QNAP subaccount."
  value       = hcloud_storage_box_subaccount.qnap_reader.server
}

output "qnap_username" {
  description = "Username for the read-only QNAP subaccount."
  value       = hcloud_storage_box_subaccount.qnap_reader.username
}

output "qnap_rclone_remote" {
  description = "Non-secret rclone SFTP endpoint summary. Port 23 enables remote checksum commands."
  value = {
    type = "sftp"
    host = hcloud_storage_box_subaccount.qnap_reader.server
    user = hcloud_storage_box_subaccount.qnap_reader.username
    port = 23
  }
}
