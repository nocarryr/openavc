# Connecting Devices Through a Bridge

Some equipment only has an RS-232 serial port, but the server running OpenAVC has no serial port near it, or the device is across the room. A **bridge** solves this. A bridge is a small box that puts a serial (or IR, or relay) port on the network, so OpenAVC can reach a serial device over Ethernet.

This guide covers serial bridges. The first supported model is the Global Cache iTach IP2SL, an Ethernet-to-RS-232 adapter.

## How it works

A bridge is a normal device in your project. You add it once, like any other device. Then any serial device you want to reach through it picks **Through a bridge** in its own Connection settings and chooses one of the bridge's ports. OpenAVC routes that device's traffic over the bridge automatically. To the rest of your project (macros, the panel, scripts) the serial device behaves exactly like a network device.

This is the same model professional control systems use for IR and serial ports: the gateway is one device, and other devices bind to its ports.

## What you need

- A serial bridge on the network with a known IP address (set a static IP or a DHCP reservation so it does not move).
- The bridge's driver installed (for the iTach IP2SL, install it from **Browse Community** in the Driver Library, or let Discovery add it for you).
- The serial device wired to the bridge with the correct RS-232 cable, and a driver for that device.

## Step 1: Add the bridge

You can add the bridge two ways:

- **Discovery.** Open **Devices**, select the **Discovery** tab, and run a scan. A supported bridge is identified automatically (the iTach announces itself on the network). Add it from the results.
- **Manually.** Click **Add Device**, pick the bridge driver, and enter its IP address.

Once added, open the bridge's device card. It shows a **Bridge Ports** section listing each port, what is currently bound to it, and a link to open the unit's own web page.

## Step 2: Connect a device through the bridge

1. Add (or edit) the serial device that is wired to the bridge, and pick its driver.
2. In **Connection settings**, the device shows a picker with three choices: **Network (IP)**, **Direct serial**, and **Through a bridge**. Choose **Through a bridge**.
3. Pick the bridge from the list, then pick the port the device is wired to (for the iTach IP2SL there is one port, "RS-232 Port 1").
4. Set the serial line settings the device expects: baud rate, parity, data bits, and stop bits. These come straight from the device's manual (for example 9600 8N1).
5. Save.

OpenAVC connects the device through the bridge and applies the serial settings to the hardware for you. The device card shows connected, and you control it like any other device.

> The connection picker only appears for drivers that support serial. A network-only device does not show it.

## Seeing the whole picture

Two places show how everything is wired:

- **The bridge's device card** lists each port and the devices bound to it.
- **The Bridge topology panel** at the top of the device list shows a tree of every bridge, its ports, and the devices on each port. Click a name to jump to that device. The panel only appears when your project has at least one bridge.

## Using the bridge on its own

A bridge device works on its own, too. Its card has the standard command sender, so you can query the unit (for example, read its firmware version) without binding anything to it. The link to the unit's web page lets you reach the manufacturer's own configuration screens.

## Troubleshooting

- **The device will not connect.** Confirm the bridge itself is online (its own device card shows connected). Check the serial settings match the device's manual exactly, including baud rate and parity.
- **No response from the device.** This is almost always wiring or line settings. RS-232 needs the correct cable. If a straight-through cable gives nothing, try a null-modem (crossover) cable, or the reverse. Double-check baud rate, data bits, parity, and stop bits against the manual.
- **The bridge is not in the bridge list.** Make sure the bridge device is added to the project first. The list shows project devices whose driver advertises bridge ports.
- **Only one connection at a time.** A single serial pass-through port carries one connection. Bind one device per serial port.

## See Also

- [Devices and Drivers](devices-and-drivers.md). Adding equipment, testing, and the driver library
- [Creating Drivers](creating-drivers.md). Building drivers, including multi-transport drivers and bridges
