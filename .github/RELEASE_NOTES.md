# OpenAVC v0.22.0

- **Control IR equipment through an IR bridge.** Add an IR bridge such as the
  Global Cache iTach IP2IR and put infrared-only gear under control: displays,
  cable boxes, projectors, anything driven by a remote. Each IR device carries
  its own code set. Search the built-in online code database, learn codes from
  the device's physical remote, or paste Pronto hex. Codes become regular
  device commands, so panel buttons, macros, and triggers drive IR gear like
  anything else.

- **Local USB serial connections.** Serial devices can connect through a
  USB-to-serial adapter plugged into the OpenAVC server. The port picker lists
  attached adapters, and the connection binds to the adapter itself rather
  than the port name the operating system assigned, so it keeps working across
  reboots and replugs.

- **Device liveness checks.** Drivers can declare a liveness check, so a
  device that stops answering is marked offline with a `no_response` reason
  instead of appearing connected. TCP connections can enable keepalive,
  offline reasons are more specific across the board, and login-protected
  telnet devices only report connected once authentication succeeds.

- **Audio-taper faders and finer slider control.** Sliders and faders gain a
  logarithmic (audio taper) response option, a send-on-release mode, and
  display formatting with decimal places and a unit label. Panel select
  elements honor per-option appearance styling.

- **Child entities in YAML drivers.** Multi-channel devices such as matrix
  switchers and multi-zone amplifiers no longer need a Python driver to expose
  per-channel controls.

- **More in the Programmer.** The dashboard QR dialog prints a wall sign for
  pairing panels to a space. Driver Builder adds a request headers editor for
  HTTP drivers, a TLS verification toggle for testing devices with self-signed
  certificates, and a transport panel that shows the defaults the runtime
  actually uses. The device simulator now covers serial drivers. Windows and
  macOS installs include the built-in starter projects.

Fixes and reliability:

- Command values are checked against the ranges a driver declares before they
  reach the device. If you use community drivers, update them when you update
  the platform so their declared ranges match.
- Plugin setup saves as you type: a config form with required fields still to
  fill saves what you have entered and reports what is missing, instead of
  rejecting the save.
- Device discovery refreshes a device's hostname and name on every scan,
  isolates driver discovery probes so a faulty one cannot stall a scan, and
  never sends the SNMP community string back to the browser.
- In-app updates on Linux and Raspberry Pi preserve the scripts directory,
  recover a broken runtime environment, and log rollback versions correctly.
- Serial flow control settings stored in existing projects now take effect.
  If a serial device stops responding after this update, check its flow
  control setting.
- Undo and redo in the UI Builder track edits reliably across page switches
  and element re-creation, and undoing a change made by the AI assistant
  restores every open editor to match.
- The icon picker only offers icons the panel can render, macro step
  drag-and-drop reorders correctly, stepped cron schedules survive the trigger
  editor, and removing a button's first action keeps the rest.
- Login credentials only attach to same-origin requests, device HTTP
  responses are size-capped, and DEBUG log lines shipped to the cloud AI have
  device, connection, and plugin credentials scrubbed.
- Panel Access shows the address you are connected on, video stream previews
  load on servers that require login, and copy buttons work over plain HTTP.
