output "public_ip_address" {
  description = "Public IP address of the Azure Linux VM"
  value       = azurerm_public_ip.pip.ip_address
}

output "ssh_command" {
  description = "SSH command for connecting to the Azure Linux VM"
  value       = "ssh -i C:/Users/Student/.ssh/azure_rsa azureuser@${azurerm_public_ip.pip.ip_address}"
}
