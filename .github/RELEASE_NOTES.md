# OpenAVC v0.15.0

v0.15.0 adds per-device quick actions and setup wizards, SSH device control, and
clearer offline diagnostics, on top of a broad reliability pass across the
platform.

## Quick actions and setup wizards

Quick Actions are handy per-device shortcuts in the device view: one-click
buttons for the commands you run while commissioning or troubleshooting a
device. And a driver can now define a setup wizard for its device, walking you
step by step through tasks like provisioning so first-time configuration is
guided rather than manual.

## Control devices over SSH

OpenAVC can now drive equipment that exposes a command-line interface over SSH,
using the system's OpenSSH client. Authenticate with a password or an installed
key. This covers network switches, servers, and appliances that speak CLI
instead of a binary control protocol.

## Know why a device went offline

When a device drops, OpenAVC tells you what happened instead of showing a
generic "disconnected." The device card reports an actionable reason such as
authentication failed, connection refused, unreachable, or a changed SSH host
key, each with a plain-language next step. Drivers can attach their own hint to
the banner for device-specific guidance.

## Touch panel theming

ThemeStudio adds per-type styling and page background editors. Style buttons,
sliders, and labels independently, and set a background image or color per page.
This release also fixes several color and contrast issues.

## Sharper device discovery

Discovery identifies more equipment, including HTTPS-only devices that
previously came back unrecognized. It reads additional vendor signals from
devices already on the network and keeps results current as a scan runs.

## Driver authoring

Import and export driver bundles straight from the Code view. Companion files
for simulation and discovery come along on install and are cleaned up on
uninstall. The general-purpose TCP driver and the Add Device dialog also pick up
authoring improvements.

## Reliability and hardening

This release includes a wide reliability pass across the platform. The scripting
runtime, plugin system, device simulator, driver loader, cloud connection,
inter-system links, scheduling and triggers, backups, and saved variable state
are all more resilient to malformed input, network failures, and edge cases.
Update and rollback handling is more dependable.
