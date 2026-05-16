OpenAVC now has built-in HTTPS that you can turn on from Settings > Security in the Programmer. Most installs stay on HTTP because they live on an isolated AV VLAN, but when you need TLS it is a one-click toggle: the server generates its own internal CA and server certificate, runs the HTTPS listener on port 8443, and keeps port 8080 alive as an HTTP-to-HTTPS redirect so existing bookmarks and panel devices keep working. You can also point it at your own internal-CA cert and key. The Programmer can now prompt you to install any community drivers a project needs but does not have, restart the server in-app after a settings change, and ships a handful of reliability fixes for busy projects.

## HTTPS

Off by default. When enabled from Settings > Security, the server runs two listeners side by side. A TLS listener on port 8443 serves the full app. A tiny HTTP listener on 8080 returns a 301 or 308 redirect to the matching HTTPS URL, preserving the path and query string, so existing bookmarks, panel apps, and mDNS clients keep working without any reconfiguration.

The auto-generated certificate has a 10-year validity. Its subject alternative names cover `localhost`, `127.0.0.1`, the OS hostname, and every local IPv4 the server can see, plus `::1` when IPv6 is up. If the host's primary IP changes between restarts the server cert is re-issued automatically against the same internal CA, so any device that already trusts the CA survives the re-issue without re-pairing. The Security card displays the certificate fingerprint and per-OS instructions for installing the CA on Windows, macOS, iOS, and Android.

If you have an internal CA, switch the mode to **Provided** in Settings > Security and point at your PEM cert and key. There is no silent fallback to HTTP on a bad cert: the server writes a precise error to startup-error.json and refuses to start the TLS listener.

mDNS advertises `scheme=https` and the TLS port when HTTPS is on, so panel apps that read the field build the right URL straight away. ISC peers, the cloud tunnel, the Windows tray, and the Pi kiosk launcher all pick up HTTPS automatically with no config changes.

## In-app server restart

The Network and Security cards now prompt you to restart the server when you save a setting that needs a process restart, and the dialog hands the restart back to the service manager. NSSM on Windows, systemd on Linux, Docker, and dev installs all work. The progress dialog tracks the new process coming up and reloads the page automatically when it is reachable again.

## Missing drivers prompt

Open a project that references a driver you do not have installed and the Programmer surfaces a modal listing every missing driver, annotated with community-catalog matches. One click installs them and re-activates the orphaned devices so you do not have to add them back to the project by hand.

## Reliability fixes

A handful of fixes that hit busy projects.

* Save conflicts and slow startup when a project has many devices.
* Device connected state lying for drivers that do not use the platform transports.
* Cloud restart hanging when the service manager could not see the process exit.
* `device.error.<id>` is now emitted from poll errors and send_command errors, not just connect errors, so error-driven triggers fire reliably.

## Polish

* The script editor's Monaco bundle is now served locally so it works offline.
* Embedded panels inside the UI Builder no longer prompt for the panel password.
* The Docker build now compiles the frontend on the native build arch, avoiding QEMU SIGILL crashes during multi-arch CI builds.
