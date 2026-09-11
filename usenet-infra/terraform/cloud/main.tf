locals {
  common_labels = merge(
    var.additional_labels,
    {
      "managed-by"  = "terraform"
      "service"     = "usenet-acquisition"
      "environment" = var.environment
    },
  )
}

data "hcloud_image" "ubuntu" {
  name              = var.image_name
  with_architecture = "x86"
}

resource "hcloud_ssh_key" "admin" {
  name       = "${var.name_prefix}-admin"
  public_key = trimspace(var.admin_ssh_public_key)
  labels     = local.common_labels
}

resource "hcloud_primary_ip" "ipv4" {
  name              = "${var.name_prefix}-ipv4"
  type              = "ipv4"
  location          = var.location
  auto_delete       = false
  delete_protection = true
  labels            = local.common_labels
}

resource "hcloud_primary_ip" "ipv6" {
  name              = "${var.name_prefix}-ipv6"
  type              = "ipv6"
  location          = var.location
  auto_delete       = false
  delete_protection = true
  labels            = local.common_labels
}

resource "hcloud_firewall" "server" {
  name   = "${var.name_prefix}-server"
  labels = local.common_labels

  dynamic "rule" {
    for_each = var.vpn_peer_ipv4 == "" ? [] : ["500", "4500"]
    content {
      direction   = "in"
      protocol    = "udp"
      port        = rule.value
      source_ips  = ["${var.vpn_peer_ipv4}/32"]
      description = "Private UI IPsec from home gateway"
    }
  }

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.admin_ssh_cidrs
    description = "Administrative SSH from trusted networks"
  }

  # ICMP/ICMPv6 is useful for diagnostics and correct path-MTU discovery.
  rule {
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "ICMP and ICMPv6"
  }
}

resource "hcloud_server" "acquisition" {
  name        = var.server_name
  server_type = var.server_type
  image       = data.hcloud_image.ubuntu.id
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.admin.id]
  firewall_ids = [
    hcloud_firewall.server.id,
  ]

  public_net {
    ipv4_enabled = true
    ipv4         = hcloud_primary_ip.ipv4.id
    ipv6_enabled = true
    ipv6         = hcloud_primary_ip.ipv6.id
  }

  labels                   = local.common_labels
  delete_protection        = true
  rebuild_protection       = true
  shutdown_before_deletion = true

  lifecycle {
    # Hetzner injects these only during creation. Rotate host keys with
    # configuration management instead of replacing the server for this list.
    ignore_changes = [ssh_keys]
  }
}
