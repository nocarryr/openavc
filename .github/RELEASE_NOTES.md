Discovery has been rebuilt around driver-declared probes and evidence, so every vendor identification on the network scan card now traces back to a probe response or a service the driver said it owns. The cloud agent now supports remote restart, diagnostic actions, and tunneled WebSocket and HTTP traffic with query strings and subprotocols intact. Matrix and audio devices respect audio-follow-video correctly. The Driver Builder's Live Test works over serial, surfaces rate-limit feedback, and guards against running against a production project. A pre-release audit ran across the platform and the findings are closed.

## Discovery

Discovery is now schema-driven. A driver declares its TCP and UDP probes (or an mDNS service, or an SNMP OID, or a small Python companion), and the scan engine runs them against the network. The result for each device records the probe that matched, the literal pattern it found, and which fields the driver extracted. The platform itself no longer carries any vendor knowledge, so adding a new device family is a driver change, not a core change.

The Driver Builder's Discovery editor has been rebuilt to match. You can write a probe inline, see which signal it provides, and validate it against shipped probe fixtures before any device is on the network. Companion `.py` files are hidden from the driver listing but install, update, and uninstall alongside their `.avcdriver` file.

A few specific hardening changes: common web-app ports are rejected as `port_open` hints because they collide with too many unrelated services. UDP reachability probes require a `poll_interval` so we don't blast the network. mDNS and SSDP scanners now bind to the configured `control_ip` instead of every interface.

## Cloud agent

Remote restart and diagnostic actions (ping a host, traceroute, DNS lookup, port check, tail logs) work end to end. The agent gates each downstream action on the capability set the cloud negotiated for the session, so an agent whose tunnel capability was revoked silently ignores stray tunnel pushes instead of acting on them.

The remote-UI tunnel now preserves query strings, custom headers, and WebSocket subprotocols. Frames that arrive before the local WebSocket finishes connecting are queued instead of dropped. The `target_port` field is honored, so the same tunnel can reach the Programmer IDE, the panel, or any other local service.

Cloud-pushed updates are now staged: the cloud download lands in a holding location, the apply step swaps atomically, and a failed apply clears the pending-update marker instead of leaving the system stuck on next boot. The Windows installer rollback now matches versions correctly across patch releases.

## Matrix and audio

Matrix mute respects audio-follow-video: muting a video route also mutes the linked audio route when the matrix is in AFV mode. Audio routes display their current source in the device test panel. The cloud's mute and route commands flow through the same AFV-aware path.

## Driver Builder Live Test

Live Test works against serial drivers in addition to TCP and HTTP. The panel refuses to run against the live project to keep an in-progress driver from clobbering a deployed room. Rate-limit errors from the device surface in the test panel directly instead of failing silently.

## Plugin hardening

A plugin that fails to register surfaces the error during install instead of disappearing. The `min_openavc_version` field is enforced at install time across both first-party and community plugins. State-pattern subscriptions with an empty pattern no longer leak state across plugin reloads.

## ISC

The inter-system connection now drops removed peers and rotates keys when auth changes, so a project reload that swaps an ISC password actually invalidates the old session. Auth failures back off with deduplicated log messages instead of spamming the log every retry interval.

## Other

* The macro engine serializes register-and-preempt within a cancel group so a fast double-tap of `system_on` / `system_off` doesn't race.
* The OSC verify path races the send socket against the listen socket for dual-port devices like grandMA3, so a verified probe doesn't depend on which socket the device replies on.
* The Python driver serial template uses the correct connection field names.
* The starter project bundled with every installer is now in the v0.4.0 schema.
* Cancelled macros are not transactional; the docs now say so.
