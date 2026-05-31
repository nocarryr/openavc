# OpenAVC v0.14.0

Better device discovery and a secure-by-default first run.

This release makes network scans identify more controllers without any setup, and changes the first-run experience so a new instance is protected from the moment it starts.

## Highlights

- **Controllers identify during a scan, even before their driver is installed.** Some telnet controllers send a Telnet negotiation in one network packet and their identifying banner in the next. Discovery now reads across packets, so devices like the TurtleAV Chazy and Darwin controllers are recognized during a network scan without installing the driver first. AMX device discovery also matches more reliably.
- **Secure by default with a first-run claim.** A brand new instance now prompts you to claim it and set a password before anything else. There is no unprotected window on first boot, and no default password to remember to change. Existing instances keep their current settings.
- **Hardened against the network.** The rate limiter no longer trusts forwarded-for headers by default, system updates verify their download and refuse to apply anything that fails the check, and several internal file-path and archive handling paths were tightened. On the Raspberry Pi image, the OS login is locked down with SSH off and a single password shared with the web login.

## Improvements

- **Device command parameters render by type.** Running a command from a device page now shows proper controls (dropdowns, number fields, toggles) instead of plain text boxes, so the right values are easier to enter.
- **Editing a device keeps its child entities.** Saving a change to a device no longer drops its sub-devices or any settings queued for an offline device.
- **Surface Configurator** gains visible-when and auto-page editors for control surfaces.
- **Per-device logs** always capture what was sent to and received from the device, and the console log honors the level you configured.
- **Video sources** send a codec hint from the discovery probe so downstream playback starts correctly.
- Driver authors can validate `.avcdriver` files live in their editor against the published schema, now linked from the docs.
