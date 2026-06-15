# Ubuntu Remote Login Input Freeze Research

Date: 2026-06-15

## Situation

- Symptom: remote access reaches an Ubuntu screen, but after a password/encryption/login screen the keyboard and mouse stop responding.
- Local probe attempted: `.agents/skills/remote-instance/scripts/remote_probe.sh --check`
- Result: SSH target `ssh -p 62001 gq@odungnest.iptime.org` returned `Permission denied (publickey,password)`, so server logs could not be inspected directly.

## Most Likely Causes

### 1. GNOME/Wayland remote desktop input/session issue

Ubuntu 22.04+ and especially 24.04 use GNOME Remote Desktop and Wayland-based sessions more often. Built-in Ubuntu Remote Login is a separate feature from desktop sharing, and Ubuntu's own test plan describes Remote Login as available from Ubuntu 24.04 LTS onward. Wayland + remote-control tools can still have compatibility or permission issues around input injection and login screens.

Clues:

- You can see the remote screen.
- Login/password screen appears.
- Keyboard/mouse stop working only in the GUI remote session.
- SSH or service access may still work separately.

Checks:

```bash
systemctl status gdm3
systemctl status gnome-remote-desktop
loginctl
grep -i wayland /etc/gdm3/custom.conf
journalctl -b -u gdm3 --no-pager | tail -200
journalctl -b --user -u gnome-remote-desktop --no-pager | tail -200
```

Common mitigation:

```bash
sudo cp /etc/gdm3/custom.conf /etc/gdm3/custom.conf.bak.$(date +%Y%m%d-%H%M%S)
sudo sed -i 's/^#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf
sudo grep -q '^WaylandEnable=false' /etc/gdm3/custom.conf || sudo sed -i '/^\[daemon\]/a WaylandEnable=false' /etc/gdm3/custom.conf
sudo systemctl restart gdm3
```

Note: restarting `gdm3` kills active GUI sessions. Prefer SSH or console access before trying this.

### 2. xrdp/Xorg missing input stack or broken xorgxrdp config

If the remote access path is xrdp, several reports point to black/blank/frozen sessions after authentication or missing keyboard/mouse input. One common Ubuntu fix is reinstalling the Xorg input meta-package:

```bash
sudo apt update
sudo apt install --reinstall xserver-xorg-input-all xorgxrdp xrdp dbus-x11
sudo systemctl restart xrdp
```

Clues:

- The xrdp login window works, then after login the screen freezes, turns black, or input is ignored.
- Problem began after `apt upgrade`.
- Same Ubuntu user is already logged in locally; xrdp can conflict with an existing graphical session.

Checks:

```bash
systemctl status xrdp xrdp-sesman
journalctl -b -u xrdp -u xrdp-sesman --no-pager | tail -300
ls -l /etc/X11/xrdp/xorg.conf
dpkg -l | egrep 'xrdp|xorgxrdp|xserver-xorg-input-all|dbus-x11'
who
loginctl list-sessions
```

### 3. Full-disk encryption/LUKS prompt before Bluetooth or wireless input is available

If "암호화면" means the boot-time disk encryption password screen, then the OS is not fully running yet. Bluetooth services and many wireless input stacks are not started before the encrypted root volume is unlocked. This is expected behavior unless the initramfs is customized.

Clues:

- Screen is the early boot disk unlock prompt, not the Ubuntu user login screen.
- Bluetooth keyboard/mouse or wireless dongle is used.
- Wired USB keyboard works.

Mitigations:

- Use wired USB keyboard for LUKS unlock.
- Use a 2.4 GHz USB dongle keyboard if the dongle behaves as USB HID at boot.
- Configure network/remote unlock or TPM/keyfile-based unlock only if the physical/security tradeoff is acceptable.

## Fast Triage Order

1. Identify the exact screen: LUKS disk unlock, GDM user login, xrdp login, or post-login desktop.
2. Get any CLI path working: SSH, TTY, IPMI/KVM, hypervisor console, or rescue mode.
3. If it is LUKS: test a wired USB keyboard first.
4. If it is Ubuntu GUI Remote Login/GNOME: inspect `gdm3`, `gnome-remote-desktop`, and Wayland state.
5. If it is xrdp: inspect `xrdp-sesman` logs and reinstall/check `xserver-xorg-input-all`, `xorgxrdp`, `dbus-x11`.
6. If input is frozen even on physical console: check kernel/hardware logs and recent package upgrades.

## Sources

- Ubuntu Wiki, Remote Desktop test plan: https://wiki.ubuntu.com/DesktopTeam/TestPlans/RemoteDesktop
- Ubuntu Discourse, Wayland sessions supporting RDP and setup location: https://discourse.ubuntu.com/t/does-rdp-on-wayland-works-what-you-recommend/22199
- Ask Ubuntu, login screen keyboard/mouse issue and `xserver-xorg-input-all`: https://askubuntu.com/questions/1135717/ubuntu-18-04-keyboard-and-mouse-not-working-at-login-screen
- xorgxrdp issue, no keyboard/mouse input over xrdp/Xorg: https://github.com/neutrinolabs/xorgxrdp/issues/164
- Ubuntu Discourse, Bluetooth keyboard not working at encryption login screen: https://discourse.ubuntu.com/t/bluetooth-keyboard-does-not-work-on-encryption-login-screen/62588
