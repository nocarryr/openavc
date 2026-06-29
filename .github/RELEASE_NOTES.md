# OpenAVC v0.21.0

- **Control MQTT devices.** Drivers can now talk to equipment over MQTT:
  televisions with a built-in broker, building-management gateways, and IoT or
  lighting bridges. It supports plain and TLS connections, including the
  self-signed certificates many devices ship with. MQTT is available to Python
  drivers.

- **Device discovery finds devices again on Linux and Raspberry Pi.** On a
  standard Linux or Pi install the network scan ran without the privilege its
  ping sweep needs, so it reported an empty network even when devices were
  present. The service now grants that privilege, and a scan finds the gear on
  your network. Discovery on Windows, Docker, and the appliance was not
  affected.

- **In-app updates are more reliable on Linux and Raspberry Pi.** Updating a
  system carried forward from an older layout could fail and leave you on the
  previous version. Changes to the background service definition (such as the
  discovery fix above) were also not applied during an update. These are fixed,
  and a failed update no longer reports itself as successful in the log.

Upgrading an existing Linux install: if device discovery still finds nothing
right after updating, re-run the install script once
(`curl -sSL https://get.openavc.com | sudo bash`) to apply the service change.
