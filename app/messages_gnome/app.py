from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GLib

from messages_gnome import APP_ID, DEFAULT_GOOGLE_ACCOUNT, __version__
from messages_gnome.constants import INTROSPECTION_XML
from messages_gnome.window import MessagesWindow


class MessagesApplication(Adw.Application):
    def __init__(self, account: str, start_hidden: bool) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._account = account or DEFAULT_GOOGLE_ACCOUNT
        self._start_hidden = start_hidden
        self._window: MessagesWindow | None = None
        self._unread = 0
        self._dbus_id = 0
        self._hold_token = None
        self.add_main_option(
            "hidden",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Start with the window hidden",
            None,
        )
        self.add_main_option(
            "account",
            ord("a"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            "Google account to sign in with",
            "EMAIL",
        )
        self.add_main_option(
            "version",
            ord("V"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Show version",
            None,
        )
        self.connect("activate", self._on_activate)
        self.connect("startup", self._on_startup)
        for name, callback in (
            ("show", lambda *_: self.show_window()),
            ("hide", lambda *_: self.hide_window()),
            ("toggle", lambda *_: self.toggle_window()),
            ("reload", lambda *_: self.reload_window()),
            ("quit", lambda *_: self.quit()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def do_handle_local_options(self, options: GLib.VariantDict) -> int:
        if options.contains("version"):
            print(f"messages-gnome {__version__}")
            return 0
        if options.contains("hidden"):
            self._start_hidden = True
        account = options.lookup_value("account", GLib.VariantType("s"))
        if account is not None:
            self._account = account.get_string()
        return -1

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        options = command_line.get_options_dict()
        hidden = options.contains("hidden")
        account = options.lookup_value("account", GLib.VariantType("s"))
        if account is not None:
            self._account = account.get_string()
        self._ensure_window()
        if not hidden:
            self.show_window()
        return 0

    def do_dbus_register(self, connection: Gio.DBusConnection, object_path: str) -> bool:
        Adw.Application.do_dbus_register(self, connection, object_path)
        info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
        self._dbus_id = connection.register_object(
            object_path,
            info.interfaces[0],
            self._on_dbus_call,
            self._on_dbus_get,
            None,
        )
        return True

    def do_dbus_unregister(self, connection: Gio.DBusConnection, object_path: str) -> None:
        if self._dbus_id:
            connection.unregister_object(self._dbus_id)
            self._dbus_id = 0
        Adw.Application.do_dbus_unregister(self, connection, object_path)

    def _on_startup(self, *_args) -> None:
        if self._hold_token is None:
            self._hold_token = self.hold()

    def _on_activate(self, *_args) -> None:
        self._ensure_window()
        self.show_window()

    def _ensure_window(self) -> MessagesWindow:
        if self._window is None:
            self._window = MessagesWindow(
                self,
                account=self._account,
                start_hidden=True,
                on_unread=self._emit_unread,
                on_visibility=lambda _visible: self._emit_props(),
            )
        return self._window

    def show_window(self) -> None:
        self._ensure_window().reveal()

    def hide_window(self) -> None:
        if self._window is not None:
            self._window.hide()

    def toggle_window(self) -> None:
        self._ensure_window().toggle()

    def reload_window(self) -> None:
        if self._window is not None:
            self._window.reload()

    def _emit_unread(self, count: int) -> None:
        self._unread = count
        conn = self.get_dbus_connection()
        path = self.get_dbus_object_path()
        if conn is None or path is None:
            return
        conn.emit_signal(
            None,
            path,
            APP_ID,
            "UnreadChanged",
            GLib.Variant("(i)", (int(count),)),
        )
        self._emit_props()

    def _emit_props(self) -> None:
        conn = self.get_dbus_connection()
        path = self.get_dbus_object_path()
        if conn is None or path is None:
            return
        conn.emit_signal(
            None,
            path,
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            GLib.Variant(
                "(sa{sv}as)",
                (
                    APP_ID,
                    {
                        "Visible": GLib.Variant("b", bool(self._window and self._window.is_visible())),
                        "UnreadCount": GLib.Variant("i", int(self._unread)),
                    },
                    [],
                ),
            ),
        )

    def _on_dbus_call(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        method_name,
        _parameters,
        invocation,
    ) -> None:
        actions = {
            "Toggle": self.toggle_window,
            "Show": self.show_window,
            "Hide": self.hide_window,
            "Reload": self.reload_window,
            "Quit": self.quit,
        }
        action = actions.get(method_name)
        if action is None:
            invocation.return_error_literal(
                Gio.io_error_quark(),
                Gio.IOErrorEnum.NOT_SUPPORTED,
                f"Unknown method {method_name}",
            )
            return
        action()
        invocation.return_value(None)

    def _on_dbus_get(self, _connection, _sender, _object_path, _interface_name, property_name):
        if property_name == "Visible":
            return GLib.Variant("b", bool(self._window and self._window.is_visible()))
        if property_name == "UnreadCount":
            return GLib.Variant("i", int(self._unread))
        return None


def run(argv: list[str] | None = None) -> int:
    Adw.init()
    app = MessagesApplication(DEFAULT_GOOGLE_ACCOUNT, False)
    args = sys.argv if argv is None else [sys.argv[0], *argv]
    return app.run(args)
