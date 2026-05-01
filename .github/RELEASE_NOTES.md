## Browse Drivers Refresh

The Browse Drivers panel in the Programmer IDE now surfaces the full driver catalog. Video, Streaming, and Power are first-class categories, and drivers using HTTP or OSC transports are now properly tagged. Each driver shows its tags, an overview of what the driver covers, the list of compatible models, and a deprecated badge when the author has marked it for replacement.

## Declarative Telnet Login

`.avcdriver` files can now declare a Telnet-style `Username:` / `Password:` login handshake without any Python. Add an `auth:` block to the driver definition and the platform handles the prompt-and-respond exchange between the TCP connect and the first command. The Atlona OmniStream and Lutron HomeWorks QS community drivers use this to support devices with login authentication enabled out of the box.

## Smarter Discovery

Network discovery now uses a curated device catalog from the community driver repo to identify equipment by exact manufacturer and model. When a scan recognizes a device that matches a known model, OpenAVC suggests the right driver directly instead of guessing from open ports.

## Programmer Login

The Programmer IDE now has its own login screen. When you set a Programmer username and password in System Settings, integrators are prompted to sign in before they can edit the project. The Panel UI is unaffected and continues to use its own access settings.

## Simulator Improvements

The auto-generated simulator now handles HTTP-based YAML drivers, so you can test REST-style devices without writing a custom `_sim.py`. The simulator also mirrors the new declarative login handshake, so drivers with `auth:` blocks can be exercised end to end without real hardware.

## Stability and Polish

- WebSocket broadcasts now fan out concurrently, smoothing out UI updates when many panels are connected to a busy room.
- Project files preserve fields they don't recognize, making it safer to roll back to an older OpenAVC after editing on a newer one.
- Plugins now use a dedicated `variable_write` capability for setting user variables, separate from plugin-namespace state writes.
- Panels can no longer write outside the `var.*` and `plugin.*` state namespaces over WebSocket.
- Programmer and Panel passwords set at runtime are enforced immediately without restarting the server.
- A new `state.delete` WebSocket message replaces the previous workaround for clearing state keys when devices are removed.
- The Programmer IDE debounces plugin event refetches, eliminating a flicker on plugin-heavy projects.

## Driver Definitions

The canonical YAML keys for command and response definitions are now `send` and `match`. The legacy `string` and `pattern` aliases still load, but the platform logs a one-time deprecation warning so driver authors can migrate at their own pace.
