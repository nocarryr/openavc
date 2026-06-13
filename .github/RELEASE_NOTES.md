# OpenAVC v0.17.1

A small fix release.

- The announcement that lets the Panel app and other devices find an OpenAVC
  server by browsing the network now starts reliably on Linux servers. It
  previously failed silently at startup on Linux installs, so automatic
  server discovery only worked against Windows servers.
