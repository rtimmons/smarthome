locals {
  common_labels = merge(
    var.additional_labels,
    {
      "managed-by"  = "terraform"
      "service"     = "usenet-catalog"
      "environment" = var.environment
    },
  )
}

resource "hcloud_storage_box" "catalog" {
  name             = var.storage_box_name
  storage_box_type = var.storage_box_type
  location         = lower(var.location)
  password         = var.storage_box_password
  ssh_keys         = var.storage_box_ssh_public_keys

  access_settings = {
    # The writer runs on Hetzner Cloud. Keeping the main account internal means
    # only the deliberately restricted QNAP subaccount is Internet-reachable.
    reachable_externally = false
    samba_enabled        = false
    ssh_enabled          = true
    webdav_enabled       = false
    zfs_enabled          = false
  }

  labels            = local.common_labels
  delete_protection = true

  lifecycle {
    prevent_destroy = true

    # Initial SSH keys cannot be updated through the Storage Box API. Without
    # this guard, changing the list forces replacement of the canonical store.
    ignore_changes = [ssh_keys]
  }
}

resource "hcloud_storage_box_subaccount" "qnap_reader" {
  storage_box_id = hcloud_storage_box.catalog.id
  name           = var.qnap_subaccount_name
  home_directory = var.qnap_home_directory
  password       = var.qnap_subaccount_password
  description    = "Read-only catalog access for the QNAP"

  access_settings = {
    reachable_externally = true
    readonly             = true
    samba_enabled        = false
    ssh_enabled          = true
    webdav_enabled       = false
  }

  labels = local.common_labels

  lifecycle {
    prevent_destroy = true
  }
}
