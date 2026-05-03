## Bug fix

In-app updates on Windows were silently failing in 0.10.0. The new installer was being downloaded and verified correctly, but it was launched as a child process of the dying server and got killed by the service manager (NSSM) before it could replace any files. The Programmer UI sat on "Restarting server" indefinitely, and the existing install kept running on the old version.

The installer now runs via Windows Task Scheduler instead of as a child process, which puts it in its own process tree outside the service manager's reach.

**To get this fix on a 0.10.0 Windows install:** the in-app updater can't deliver it (because 0.10.0 has the broken code that this release fixes). Manually run the 0.10.1 installer once. Future updates from 0.10.1 forward will work normally.

Linux, Raspberry Pi, and Docker were unaffected.
