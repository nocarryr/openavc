#!/bin/bash -e
# Final system configuration: user, services, auto-login, kiosk integration.

OPENAVC_USER="openavc"
DATA_DIR="/var/lib/openavc"

# --- User and permissions ---
#
# The 'openavc' user is created by pi-gen's stage1 from FIRST_USER_NAME
# with the password from FIRST_USER_PASS. The first-boot rename wizard is
# skipped via DISABLE_FIRST_BOOT_USER_RENAME=1 in config, so the user we
# get out of stage1 is the user the system boots into.
chown -R "$OPENAVC_USER:$OPENAVC_USER" /opt/openavc
chown -R "$OPENAVC_USER:$OPENAVC_USER" "$DATA_DIR"
mkdir -p /var/log/openavc
chown -R "$OPENAVC_USER:$OPENAVC_USER" /var/log/openavc

# Add openavc user to video and input groups (needed for display + touch)
usermod -aG video,input,dialout "$OPENAVC_USER"

# Allow passwordless reboot from the server (used by Programmer UI reboot button)
echo "$OPENAVC_USER ALL=(ALL) NOPASSWD: /sbin/reboot" > /etc/sudoers.d/openavc-reboot
chmod 440 /etc/sudoers.d/openavc-reboot

# --- Enable services ---

# Defensive: even with DISABLE_FIRST_BOOT_USER_RENAME=1, the userconf-pi
# package is still installed by export-image/01-user-rename/00-packages,
# so the userconfig.service unit file remains on disk (just not enabled).
# Disable it explicitly in case a future package update or postinst
# enables it. See pi-gen issue #913.
systemctl disable userconfig.service 2>/dev/null || true

systemctl enable openavc.service
# Note: openavc-panel.service is NOT enabled. The kiosk is launched from
# the labwc autostart instead, which runs inside the graphical session
# and has proper access to the Wayland display.
systemctl enable openavc-firstboot.service
systemctl enable avahi-daemon.service

# Create first-boot marker
touch "$DATA_DIR/.firstboot"

# --- Auto-login for kiosk display ---

# Configure auto-login so the desktop session starts without interaction.
# This is required for the kiosk display to work (Chromium needs a
# graphical session). If no display is connected, the desktop session
# starts but has no visible output. The server runs regardless.

# Raspberry Pi OS uses lightdm for display management
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
if [ -f "$LIGHTDM_CONF" ]; then
    # Set auto-login user — handles both commented and uncommented lines
    # (Pi OS may already have autologin-user=rpi-first-boot-wizard set)
    if grep -q "^autologin-user=" "$LIGHTDM_CONF"; then
        sed -i "s/^autologin-user=.*/autologin-user=$OPENAVC_USER/" "$LIGHTDM_CONF"
    elif grep -q "^#autologin-user=" "$LIGHTDM_CONF"; then
        sed -i "s/^#autologin-user=.*/autologin-user=$OPENAVC_USER/" "$LIGHTDM_CONF"
    else
        sed -i "/^\[Seat:\*\]/a autologin-user=$OPENAVC_USER" "$LIGHTDM_CONF"
    fi
fi

# Also configure via raspi-config nonint (belt and suspenders)
if command -v raspi-config &> /dev/null; then
    raspi-config nonint do_boot_behaviour B4 2>/dev/null || true
fi

# --- Kiosk display integration ---

# --- labwc display configuration ---
#
# RPi OS runs labwc via labwc-pi which passes -m (merge-config), so both
# the system autostart (/etc/xdg/labwc/autostart) and user autostart run.
# We must strip the desktop shell from the system autostart, otherwise
# pcmanfm (wallpaper + icons) and wf-panel-pi (taskbar) appear before
# Chromium loads, and users can interact with them.

OPENAVC_HOME="/home/$OPENAVC_USER"
LABWC_DIR="$OPENAVC_HOME/.config/labwc"
mkdir -p "$LABWC_DIR"

# Replace system autostart: remove desktop shell, keep display detection
SYSTEM_AUTOSTART="/etc/xdg/labwc/autostart"
if [ -f "$SYSTEM_AUTOSTART" ]; then
    cat > "$SYSTEM_AUTOSTART" << 'SYSAUTO'
# OpenAVC: desktop shell removed (no pcmanfm, no wf-panel-pi)
/usr/bin/kanshi &
SYSAUTO
fi

# User autostart: launch OpenAVC display (panel or info screen)
cat > "$LABWC_DIR/autostart" << 'AUTOSTART'
/opt/openavc/scripts/panel-kiosk.sh &
AUTOSTART

# User rc.xml: disable touch mouse emulation for native swipe scrolling,
# remove window decorations from Chromium, and force fullscreen on first map
# (workaround for labwc/Chromium race condition — labwc issue #1994)
cat > "$LABWC_DIR/rc.xml" << 'RCXML'
<?xml version="1.0"?>
<labwc_config>
  <touch deviceName="" mouseEmulation="no"/>
  <windowRules>
    <windowRule identifier="chromium">
      <serverDecoration>no</serverDecoration>
      <skipTaskbar>yes</skipTaskbar>
      <onFirstMap>
        <action name="ToggleFullscreen"/>
      </onFirstMap>
    </windowRule>
  </windowRules>
</labwc_config>
RCXML

chown -R "$OPENAVC_USER:$OPENAVC_USER" "$OPENAVC_HOME/.config"

# --- Disable screen blanking (system-wide) ---

# Prevent DPMS from turning off the display
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/10-no-blanking.conf << 'XCONF'
Section "ServerFlags"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection
XCONF

# --- SSH banner ---

cat > /etc/motd << 'MOTD'

  ╔═══════════════════════════════════════╗
  ║         OpenAVC Room Control          ║
  ╠═══════════════════════════════════════╣
  ║  Programmer: http://openavc.local     ║
  ║  Panel:      http://openavc.local/p   ║
  ║  API:        http://openavc.local/api ║
  ╚═══════════════════════════════════════╝

MOTD

# --- Copy seed project if not already present ---

SEED_PROJECT="/opt/openavc/installer/seed/default/project.avc"
TARGET_PROJECT="$DATA_DIR/projects/default/project.avc"
if [ -f "$SEED_PROJECT" ] && [ ! -f "$TARGET_PROJECT" ]; then
    mkdir -p "$(dirname "$TARGET_PROJECT")"
    cp "$SEED_PROJECT" "$TARGET_PROJECT"
    chown "$OPENAVC_USER:$OPENAVC_USER" "$TARGET_PROJECT"
fi

# --- Build verification ---
#
# Hard-check the final image state. If any of these fail, abort the build
# rather than producing an image that boots into the wrong user / blank
# desktop. Every check here corresponds to a real failure mode we have
# previously shipped.
echo "=== OpenAVC pi-image build verification ==="
errors=0

if ! id "$OPENAVC_USER" >/dev/null 2>&1; then
    echo "FATAL: $OPENAVC_USER user does not exist"
    errors=$((errors + 1))
fi

if id rpi-first-boot-wizard >/dev/null 2>&1; then
    echo "FATAL: rpi-first-boot-wizard user still exists (userconf-pi purge incomplete)"
    errors=$((errors + 1))
fi

if [ -f "$LIGHTDM_CONF" ]; then
    if ! grep -q "^autologin-user=$OPENAVC_USER\$" "$LIGHTDM_CONF"; then
        echo "FATAL: lightdm autologin-user is not '$OPENAVC_USER':"
        grep -i autologin "$LIGHTDM_CONF" || echo "  (no autologin-user line found)"
        errors=$((errors + 1))
    fi
else
    echo "FATAL: $LIGHTDM_CONF does not exist"
    errors=$((errors + 1))
fi

state=$(systemctl is-enabled userconfig.service 2>&1 || true)
case "$state" in
    masked|disabled|not-found) ;;
    *)
        echo "FATAL: userconfig.service is in unexpected state: $state"
        errors=$((errors + 1))
        ;;
esac

if [ -e /etc/xdg/autostart/piwiz.desktop ]; then
    echo "FATAL: piwiz.desktop autostart still present"
    errors=$((errors + 1))
fi

if [ ! -f "$LABWC_DIR/autostart" ]; then
    echo "FATAL: openavc labwc autostart missing at $LABWC_DIR/autostart"
    errors=$((errors + 1))
fi

if [ "$errors" -gt 0 ]; then
    echo "Pi-image build aborted: $errors verification error(s) above"
    exit 1
fi

echo "Pi-image build verification: OK"
echo "OpenAVC Pi image configuration complete."
