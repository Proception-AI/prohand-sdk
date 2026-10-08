# Linux udev rules — Proception driver

Grant non-root access to ProHand / ProGlove USB devices.

## Install
    ./install-udev-rules.sh           # install *.rules into /etc/udev/rules.d/, reload udev
    ./install-udev-rules.sh --check   # show install status
    ./install-udev-rules.sh --remove  # uninstall

After installing, unplug and replug the device. The rules set
`GROUP="plugdev"`, so your user should be in the `plugdev` group.
