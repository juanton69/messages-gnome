# Google Messages for GNOME

A GNOME Shell 51 extension plus a GTK4 / libadwaita helper that wraps [Messages for web](https://messages.google.com/web). Left-click the top-bar icon to show or hide the window. Right-click opens a small menu.

This is not affiliated with Google. There is no public Messages API; texting still runs through your Android phone.

Default Google account: **juanton@wahcha.com**

Repository: https://github.com/juanton69/messages-gnome

## What you get

- A chat icon in the GNOME top bar
- Single left-click shows or hides the Messages window
- Right-click: open/hide, reload, settings, quit
- Unread badge on the icon
- Persistent login in `~/.local/share/messages-gnome`
- GNOME notifications for incoming texts
- Optional forward of SMS codes to the local [otp-grabber](https://github.com/juanton69/otp-grabber) socket

## Requirements

Fedora 45 Workstation with GNOME Shell 51:

- `python3-gobject`, `gtk4`, `libadwaita`, `webkitgtk6.0`
- An Android phone with Google Messages on the same Google account

## Install

```bash
chmod +x install.sh uninstall.sh
./install.sh
```

`install.sh` stops and uninstalls the old KDE `messages-kde` client. The git checkout at `~/messages-kde` is left in place.

Then **log out and back in**. GNOME Shell 51 only discovers a new extension UUID at session start.

After login, left-click the Messages icon in the top bar. Sign in as `juanton@wahcha.com` and confirm the pairing prompt on your phone. This WebKit session is separate from the old Qt client, so you will pair this computer again.

## Settings

`gnome-extensions prefs google-messages@juanton.local`

- Google account used for the sign-in hint
- Start the helper hidden until the first click

## Uninstall

```bash
./uninstall.sh          # keep saved login
./uninstall.sh --purge  # also delete cookies and cache
```

## License

[GPL-3.0-or-later](LICENSE)
