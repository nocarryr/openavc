## Bug fix

The Reboot button in System Settings on Raspberry Pi deployments did nothing. The API endpoint was being called correctly, but `sudo reboot` was silently failing because the bare command resolved to a path not covered by the sudoers rule. The reboot now works.
