# OpenAVC v0.23.0

- **Wireless presentation.** The new Present plugin turns an OpenAVC system
  into a wireless presentation gateway. Guests browse to the connect address
  shown for the space and share their screen from the browser, with no app
  install and no login. Displays join from any browser, or drive an output
  connected to the OpenAVC server itself, and a routing matrix picks which
  presenter shows on which display. The Programmer manages displays, links,
  and routing from the plugin's page, and shows who is presenting. Install
  Present from Browse Plugins; it requires this release. Under the hood,
  plugins can now serve guest pages that work without a login, a capability
  open to every plugin developer.

- **Browser-trusted HTTPS.** Systems paired with OpenAVC Cloud can turn on a
  trusted certificate in Settings > Security with one click. The cloud
  obtains a publicly trusted certificate for the system (the private key
  never leaves your server), and browsers land on a certified URL with a
  normal padlock: nothing to install on any client device, which makes
  HTTPS practical for guest and BYOD scenarios. Clients that cannot resolve
  the certified name fall back to the bare-IP address automatically. The
  HTTPS listener also enforces TLS 1.2 or newer with modern ciphers, and the
  self-signed listener now serves its full certificate chain.

- **Short URLs.** Turn on Short URLs in Settings > Network and typing the
  bare address works: `http://192.168.1.20/panel` instead of
  `http://192.168.1.20:8080/panel`. It composes with HTTPS and trusted
  certificates, so a bare IP can land directly on the padlocked page. On
  Windows, Linux, and Raspberry Pi the OS firewall now follows the features
  you enable, so turning on HTTPS or Short URLs never needs a manual
  firewall edit.

- **Devices that report changes on their own.** Drivers can now receive
  device-initiated updates instead of waiting for the next poll: a TCP port
  the device dials back to, inbound HTTP callbacks, server-sent event
  streams, and multicast announcements all feed the same response rules.
  A new connection watchdog marks a silent device offline, and response
  throttling keeps chatty devices from flooding state. The Driver Builder
  gets editors for both, so volume moved at the wall or an input switched
  at the device shows up on panels immediately.

- **Faster, safer project saves.** Saving in the Programmer now applies only
  what changed instead of rebuilding the whole runtime, so editing a UI page
  or a macro no longer bounces devices. Large projects serialize in the
  background without freezing the editor, and two sessions editing the same
  project get a conflict prompt instead of silently overwriting each other.

- **Richer YAML drivers.** Command parameters and device settings can carry
  human-readable value labels. Config fields gain typed defaults, a float
  type, and a table type with a row editor on the device page. Commands can
  declare shared prefix/suffix framing or computed-length binary framing.
  Connect and poll queries can be gated on a config field, and child entity
  rosters can follow a count the device reports, so one driver fits the
  8-channel and 16-channel model. The Driver Builder authors all of it.

- **Easier panel binding.** Shows > Value walks you through a guided
  Device to Property picker with friendly names, a Match Driver Range button
  fills slider bounds from what the driver declares, and value pickers use
  driver-declared units and control hints, including for child entities.

Fixes and reliability:

- Devices controlled over HTTPS now verify TLS certificates by default. If
  an HTTPS device drops offline after this update with reason
  `tls_cert_untrusted`, turn off Verify SSL Certificate for that device or
  install a trusted certificate on it.
- Text comparisons in macro conditions and triggers now ignore case, and a
  condition on a missing value no longer counts as a match.
- Login brute-force attempts are throttled on every access tier, WebSocket
  connections and frame sizes are capped, UDP and OSC replies are accepted
  only from the targeted device, and the simulator API rejects cross-site
  requests.
- Automatic update checks run daily instead of hourly, pre-release version
  ordering is handled correctly, rollbacks restart cleanly, and the Windows
  tray Check for Updates opens the right page and surfaces available
  updates.
- Update backups are kept and pruned by age, fixing version-number ordering
  that could prune the wrong backup.
- Projects migrated from very old format versions keep their device groups.
- Discovery matches SSDP fingerprints against every advertised device type,
  skips malformed community catalog entries instead of aborting the scan,
  understands more OUI hint formats, and rate-limits its probes.
- Device simulator: HTTP simulators send proper response headers, failed
  starts release their port, serial and raw-path polling are covered, and
  simulated state machines resolve transitions in a predictable order.
- Raspberry Pi image: the boot info screen service is enabled so a
  freshly-imaged Pi shows its address on the connected display, and the
  Stream Deck udev rule is scoped to the plugdev group.
- Programmer: the restart dialog no longer misreads a slow restart as a
  certificate error, macro steps edit with typed value fields and event
  payload authoring, the script console links jump to the right line, the
  System Log device filter works, and community driver updates are offered
  for drivers installed before version tracking.
- Variables coerce boolean values correctly, and renaming a variable only
  rewrites the macros that actually reference it.
- Cloud connections validate session rotation and protocol version, resend
  reliably after reconnect, and AI assistant errors surface as readable
  messages instead of raw failures.
