// SPDX-License-Identifier: GPL-3.0-or-later
// Top-bar Google Messages client for GNOME Shell 51.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const APP_BUS_NAME = 'org.juanton.MessagesGnome';
const APP_OBJECT_PATH = '/org/juanton/MessagesGnome';
const APP_INTERFACE = 'org.juanton.MessagesGnome';
const STATUS_ROLE = 'google-messages';
const HELPER_BIN = `${GLib.get_home_dir()}/.local/bin/messages-gnome`;

function spawnHelper(account, startHidden) {
    const argv = [HELPER_BIN];
    if (account)
        argv.push(`--account=${account}`);
    if (startHidden)
        argv.push('--hidden');
    try {
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
        return true;
    } catch (error) {
        console.warn(`google-messages: failed to start helper: ${error.message}`);
        return false;
    }
}

const MessagesIndicator = GObject.registerClass(
class MessagesIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.5, 'Google Messages');
        this._extension = extension;
        this._proxy = null;
        this._watchId = 0;
        this._ownerId = 0;
        this._signalId = 0;
        this._startId = 0;
        this._unread = 0;

        const box = new St.BoxLayout({style_class: 'panel-status-menu-box google-messages-panel-box'});
        const iconFile = Gio.File.new_for_path(`${extension.path}/icons/google-messages-symbolic.svg`);
        this._icon = new St.Icon({
            gicon: new Gio.FileIcon({file: iconFile}),
            style_class: 'system-status-icon',
            icon_size: 16,
        });
        this._badge = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'google-messages-badge',
            visible: false,
        });
        box.add_child(this._icon);
        box.add_child(this._badge);
        this.add_child(box);

        if (this._clickGesture)
            this._clickGesture.set_enabled(false);
        this._primaryGesture = new Clutter.ClickGesture({
            required_button: Clutter.BUTTON_PRIMARY,
            recognize_on_press: true,
        });
        this._primaryGesture.connect('recognize', () => this._toggle());
        this.add_action(this._primaryGesture);

        this._secondaryGesture = new Clutter.ClickGesture({
            required_button: Clutter.BUTTON_SECONDARY,
            recognize_on_press: true,
        });
        this._secondaryGesture.connect('recognize', () => this.menu.toggle());
        this.add_action(this._secondaryGesture);

        this._openItem = new PopupMenu.PopupMenuItem('Open Messages');
        this._openItem.connect('activate', () => this._toggle());
        this.menu.addMenuItem(this._openItem);
        const reloadItem = new PopupMenu.PopupMenuItem('Reload');
        reloadItem.connect('activate', () => this._call('Reload'));
        this.menu.addMenuItem(reloadItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const prefsItem = new PopupMenu.PopupMenuItem('Settings…');
        prefsItem.connect('activate', () => this._extension.openPreferences());
        this.menu.addMenuItem(prefsItem);
        const quitItem = new PopupMenu.PopupMenuItem('Quit');
        quitItem.connect('activate', () => this._call('Quit'));
        this.menu.addMenuItem(quitItem);

        this.menu.connect('open-state-changed', (_menu, isOpen) => {
            if (isOpen)
                this._syncMenu();
        });

        this._watchId = Gio.DBus.session.watch_name(
            APP_BUS_NAME,
            Gio.BusNameWatcherFlags.NONE,
            () => this._onNameAppeared(),
            () => this._onNameVanished());
    }

    _onDestroy() {
        if (this._startId) {
            GLib.source_remove(this._startId);
            this._startId = 0;
        }
        if (this._signalId && this._proxy) {
            this._proxy.disconnect(this._signalId);
            this._signalId = 0;
        }
        if (this._watchId) {
            Gio.DBus.session.unwatch_name(this._watchId);
            this._watchId = 0;
        }
        this._proxy = null;
        super._onDestroy();
    }

    _syncMenu() {
        let visible = false;
        if (this._proxy) {
            try {
                visible = Boolean(this._proxy.get_cached_property('Visible')?.unpack());
            } catch (error) {
                visible = false;
            }
        }
        if (visible)
            this._openItem.label.text = 'Hide Messages';
        else if (this._unread)
            this._openItem.label.text = `Open Messages (${this._unread})`;
        else
            this._openItem.label.text = 'Open Messages';
    }

    _setUnread(count) {
        this._unread = Math.max(0, count | 0);
        if (this._unread > 0) {
            this._badge.text = this._unread > 9 ? '9+' : `${this._unread}`;
            this._badge.visible = true;
        } else {
            this._badge.visible = false;
        }
    }

    _ensureHelper() {
        if (this._proxy)
            return;
        const settings = this._extension.getSettings();
        spawnHelper(
            settings.get_string('google-account'),
            settings.get_boolean('start-hidden'));
    }

    _toggle() {
        if (this._proxy) {
            this._call('Toggle');
            return;
        }
        this._ensureHelper();
        if (this._startId)
            GLib.source_remove(this._startId);
        this._startId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 400, () => {
            this._startId = 0;
            this._call('Toggle');
            return GLib.SOURCE_REMOVE;
        });
    }

    _call(method) {
        if (!this._proxy) {
            this._ensureHelper();
            return;
        }
        this._proxy.call(
            method,
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (proxy, result) => {
                try {
                    proxy.call_finish(result);
                } catch (error) {
                    console.warn(`google-messages: ${method} failed: ${error.message}`);
                }
            });
    }

    _onNameAppeared() {
        Gio.DBusProxy.new(
            Gio.DBus.session,
            Gio.DBusProxyFlags.NONE,
            null,
            APP_BUS_NAME,
            APP_OBJECT_PATH,
            APP_INTERFACE,
            null,
            (proxy, result) => {
                try {
                    this._proxy = Gio.DBusProxy.new_finish(result);
                } catch (error) {
                    console.warn(`google-messages: proxy failed: ${error.message}`);
                    this._proxy = null;
                    return;
                }
                this._signalId = this._proxy.connect('g-signal', (_p, _sender, signal, params) => {
                    if (signal === 'UnreadChanged')
                        this._setUnread(params.deepUnpack()[0]);
                });
                try {
                    const unread = this._proxy.get_cached_property('UnreadCount');
                    if (unread)
                        this._setUnread(unread.unpack());
                } catch (error) {
                    // Helper may still be starting.
                }
            });
    }

    _onNameVanished() {
        if (this._signalId && this._proxy)
            this._proxy.disconnect(this._signalId);
        this._signalId = 0;
        this._proxy = null;
        this._setUnread(0);
    }
});

export default class GoogleMessagesExtension extends Extension {
    enable() {
        this._indicator = new MessagesIndicator(this);
        Main.panel.addToStatusArea(STATUS_ROLE, this._indicator, 1, 'right');
        const settings = this.getSettings();
        spawnHelper(settings.get_string('google-account'), settings.get_boolean('start-hidden'));
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
