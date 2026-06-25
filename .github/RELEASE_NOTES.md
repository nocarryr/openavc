# OpenAVC v0.19.1

- **macOS: cloud connection now works after pairing.** On the macOS build,
  pairing an instance to the cloud reported success but the connection stayed
  disconnected, so remote access and monitoring never came online. The
  packaged app now trusts the cloud's security certificate correctly, and the
  agent connects right after pairing. Windows and Linux installs were not
  affected.
