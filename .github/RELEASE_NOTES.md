This release is about devices that contain devices. A single controller, whether that is an AV-over-IP system, a video matrix, a multi-zone amplifier, or a bank of presets, can now expose every encoder, decoder, output, zone, or preset as its own controllable entity. 0.13.0 also brings live video to the panel through the new Video Panel plugin, moves your community drivers and plugins into the data directory so they survive upgrades, and lets macros move the operator between panel pages.

## Child entities

A driver can now declare child entity types, and the platform tracks each child as its own addressable unit. A matrix shows up as one device, but each input and output is an entity you can command, bind to a button, and read state from. The same goes for the zones on a DSP, the presets on a video wall, or the encoders and decoders on an AV-over-IP system.

The Programmer gains a Child Entities tab on the device view. It lists every child with a searchable command picker and one unified filter that spans both device state and child entities, so a controller with hundreds of children stays manageable. Live child state lives in the state store under `device.<id>.<child_type>.<padded_id>.<property>`, and every child carries an `online` flag. Macros, triggers, scripts, and plugins all read and act on child state the same way they do for any device.

Child state also relays to the cloud. A driver can tag a child property with a priority so latency-sensitive state like video routing goes up quickly while bulk per-child telemetry relays on a slower cadence, and large snapshots are paced so a controller with thousands of children does not flood the link.

The project file moves to v0.5.0 to store per-child labels and config. Projects upgrade automatically, and projects without controller-style devices are unaffected.

## Video Panel

The new Video Panel plugin shows live H.264 and H.265 video on the panel. Point it at an IP camera or another RTSP source and place the stream on a panel page for a confidence monitor, a camera feed, or an overflow display. Streams are set up from a Video Streams panel in the Project view. Install it from the plugin library once you are on 0.13.0.

## Where drivers and plugins live

Community drivers and plugins now live under the data directory, for example `/var/lib/openavc` on Linux, instead of beside the program files. This keeps your installed drivers and plugins intact across upgrades and reinstalls. Existing installs migrate automatically the first time the server starts after the update, on Windows, Linux, Docker, and the Pi image.

## Page navigation from macros

A new `ui.navigate` macro step lets a macro switch the panel to another page, so a single button can run its actions and move the operator to the right screen. It understands `$back`, which walks back through the page history.

## Plugins

Plugins can now register their own HTTP routes, ship custom panel elements that appear in the UI Builder, and keep a per-plugin persistent data directory. These are the building blocks behind Video Panel, and they are available to any community plugin.

## Reliability and polish

* Discovery now pre-fills a driver's default settings when you add a discovered device, so it lands ready to connect.
* Faster state handling on large projects, through a state-key prefix index and bulk subscriptions.
* Some plugins would not enable on a fresh install, and the Enable button gave no feedback when that happened. Both are fixed: the missing dependency is bundled now, and plugin enable, disable, and settings errors surface in the Programmer instead of failing quietly.
* Uninstalling a plugin updates the project revision so other open editors notice the change.
* Custom plugin panel elements no longer interfere with editing project state and config.
