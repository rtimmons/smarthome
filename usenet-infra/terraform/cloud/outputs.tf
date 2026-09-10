output "server_id" {
  description = "Hetzner Cloud server ID."
  value       = hcloud_server.acquisition.id
}

output "server_name" {
  description = "Acquisition server name."
  value       = hcloud_server.acquisition.name
}

output "server_ipv4" {
  description = "Stable public IPv4 address assigned to the server."
  value       = hcloud_primary_ip.ipv4.ip_address
}

output "server_ipv6_network" {
  description = "Stable public IPv6 network assigned to the server."
  value       = hcloud_primary_ip.ipv6.ip_network
}

output "server_primary_ipv6" {
  description = "First usable IPv6 address configured on the server."
  value       = hcloud_server.acquisition.ipv6_address
}

output "admin_ssh_command" {
  description = "Convenience command for the initial Ubuntu image login."
  value       = "ssh root@${hcloud_primary_ip.ipv4.ip_address}"
}
