# OpenAVC v0.19.0

- **Run OpenAVC on a Mac.** There is now a macOS installer (.pkg). It sets
  OpenAVC up as a background service that starts at boot, adds a menu-bar app
  for opening the Programmer and checking status, and supports in-app updates
  and rollback the same way the Windows and Linux builds do.

- **Control a device that has no driver yet.** New Generic device types (TCP,
  serial, and HTTP) let you type a device's commands and responses directly in
  the Programmer, with no driver file. Define commands with fill-in values,
  turn replies into device state, and poll for status on an interval. Useful
  for one-off gear or for trying a protocol before writing a full driver.

- **Reach serial devices through a network bridge.** A serial device can now
  connect through an IP-to-serial gateway such as a Global Cache iTach. Point
  the device at a bridge port and OpenAVC carries its traffic over the network,
  so gear without an Ethernet port still works from anywhere on the LAN.

- **Steadier connections.** Devices on TCP, serial, UDP, and OSC now notice a
  dropped link right away and reconnect, instead of waiting out a timeout. OSC
  devices can also run over TCP.

- **Driver Builder improvements.** The Driver Builder now validates commands,
  responses, state variables, and frame settings as you build, handles child
  devices more reliably, and lets you author device settings that send OSC
  arguments or HTTP bodies and headers.

- **Fixes.** Fixes to the Plugins and Variables screens, sturdier reconnection
  in the Programmer, and connection-handling fixes across the transports.
