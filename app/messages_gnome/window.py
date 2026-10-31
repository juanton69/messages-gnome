from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GLib, Gtk, WebKit

from messages_gnome import APP_DISPLAY_NAME, APP_ID, DEFAULT_GOOGLE_ACCOUNT
from messages_gnome.constants import (
    CONVERSATIONS_URL,
    EXTERNAL_HOST_SUFFIXES,
    INTERNAL_HOST_SUFFIXES,
    LOGIN_HINT_JS,
    UNREAD_COUNT_JS,
    USER_AGENT,
    account_chooser_url,
)
from messages_gnome.otp_forward import forward_sms


def _host_matches(host: str, suffix: str) -> bool:
    host = (host or "").lower().rstrip(".")
    suffix = suffix.lower().rstrip(".")
    return host == suffix or host.endswith("." + suffix)


def _is_internal(host: str) -> bool:
    if any(_host_matches(host, suffix) for suffix in EXTERNAL_HOST_SUFFIXES):
        return False
    return any(_host_matches(host, suffix) for suffix in INTERNAL_HOST_SUFFIXES)


def _open_external(uri: str) -> bool:
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
        return True
    except Exception:
        return False


def data_dir() -> Path:
    path = Path(GLib.get_user_data_dir()) / "messages-gnome"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = Path(GLib.get_user_cache_dir()) / "messages-gnome"
    path.mkdir(parents=True, exist_ok=True)
    return path


class MessagesWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        application: Adw.Application,
        *,
        account: str,
        start_hidden: bool,
        on_unread: Callable[[int], None] | None = None,
        on_visibility: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__(application=application, title=APP_DISPLAY_NAME)
        self.set_default_size(1180, 780)
        self.set_icon_name(APP_ID)
        self._account = account or DEFAULT_GOOGLE_ACCOUNT
        self._on_unread = on_unread
        self._on_visibility = on_visibility
        self._unread = 0
        self._poll_id = 0
        self._session_ready = False

        session = WebKit.NetworkSession.new(str(data_dir() / "webkit"), str(cache_dir() / "webkit"))
        session.set_itp_enabled(False)
        session.set_persistent_credential_storage_enabled(True)
        cookies = session.get_cookie_manager()
        cookies.set_accept_policy(WebKit.CookieAcceptPolicy.ALWAYS)
        cookies.set_persistent_storage(str(data_dir() / "cookies.sqlite"), WebKit.CookiePersistentStorage.SQLITE)

        self._view = WebKit.WebView(network_session=session)
        settings = self._view.get_settings()
        settings.set_user_agent(USER_AGENT)
        settings.set_enable_javascript(True)
        settings.set_enable_javascript_markup(True)
        settings.set_javascript_can_access_clipboard(True)
        settings.set_javascript_can_open_windows_automatically(True)
        settings.set_enable_media(True)
        settings.set_enable_media_stream(True)
        settings.set_enable_mediasource(True)
        settings.set_enable_webrtc(True)
        settings.set_enable_smooth_scrolling(True)
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_enable_developer_extras(False)

        self._wire_view(self._view)
        self._view.connect("show-notification", self._on_web_notification)
        self._view.connect("load-changed", self._on_load_changed)
        self._view.connect("notify::title", self._on_title)
        self._view.connect("close", lambda *_: self.hide())

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=APP_DISPLAY_NAME, subtitle=self._account))
        reload_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text("Reload")
        reload_btn.connect("clicked", lambda *_: self._view.reload())
        header.pack_start(reload_btn)
        toolbar.add_top_bar(header)
        toolbar.set_content(self._view)
        self.set_content(toolbar)

        self.set_hide_on_close(True)
        self.connect("close-request", self._on_close)
        self.connect("notify::visible", self._on_visible)

        marker = data_dir() / "session-ready"
        if marker.exists():
            self._view.load_uri(CONVERSATIONS_URL)
        else:
            self._view.load_uri(account_chooser_url(self._account))

        if not start_hidden:
            self.present()

        self._poll_id = GLib.timeout_add_seconds(4, self._poll_unread)

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.reveal()

    def reveal(self) -> None:
        self.present()
        self.unminimize()

    def reload(self) -> None:
        self._view.reload()

    def _on_close(self, *_args) -> bool:
        self.hide()
        return True

    def _on_visible(self, *_args) -> None:
        if self._on_visibility:
            self._on_visibility(self.is_visible())

    def _on_title(self, *_args) -> None:
        title = self._view.get_title() or ""
        if title.startswith("(") and ")" in title:
            digits = title[1 : title.find(")")]
            if digits.isdigit():
                self._set_unread(int(digits))

    def _on_load_changed(self, _view, event: WebKit.LoadEvent) -> None:
        if event != WebKit.LoadEvent.FINISHED:
            return
        uri = self._view.get_uri() or ""
        host = urlparse(uri).hostname or ""
        if "accounts.google.com" in host:
            script = LOGIN_HINT_JS.replace("%EMAIL%", json.dumps(self._account))
            self._view.evaluate_javascript(script, -1, None, None, None, None)
        if "messages.google.com" in host:
            (data_dir() / "session-ready").write_text("1", encoding="utf-8")
        self._poll_unread()

    def _poll_unread(self) -> bool:
        self._view.evaluate_javascript(
            UNREAD_COUNT_JS, -1, None, None, None, self._unread_finished
        )
        return True

    def _unread_finished(self, view: WebKit.WebView, result: Gio.AsyncResult) -> None:
        try:
            value = view.evaluate_javascript_finish(result)
            count = int(value.to_int32()) if value is not None else 0
        except Exception:
            return
        self._set_unread(count)

    def _set_unread(self, count: int) -> None:
        count = max(0, int(count))
        if count == self._unread:
            return
        self._unread = count
        self.set_title(APP_DISPLAY_NAME if count == 0 else f"{APP_DISPLAY_NAME} ({count})")
        if self._on_unread:
            self._on_unread(count)

    def _wire_view(self, view: WebKit.WebView) -> None:
        view.connect("decide-policy", self._on_decide_policy)
        view.connect("permission-request", self._on_permission)
        view.connect("create", self._on_create)

    def _on_permission(self, _view, request) -> bool:
        request.allow()
        return True

    def _on_web_notification(self, _view, notification: WebKit.Notification) -> bool:
        title = notification.get_title() or APP_DISPLAY_NAME
        body = notification.get_body() or ""
        app = self.get_application()
        if app is not None:
            note = Gio.Notification.new(title)
            note.set_body(body)
            note.set_default_action("app.show")
            app.send_notification(notification.get_id() or "message", note)
        forward_sms(title, body)
        notification.connect("clicked", lambda *_: self.reveal())
        return True

    def _on_decide_policy(self, _view, decision, decision_type) -> bool:
        if decision_type not in (
            WebKit.PolicyDecisionType.NAVIGATION_ACTION,
            WebKit.PolicyDecisionType.NEW_WINDOW_ACTION,
        ):
            return False
        try:
            action = decision.get_navigation_action()
            request = action.get_request()
            uri = request.get_uri() or ""
            nav_type = action.get_navigation_type()
        except Exception:
            return False

        parsed = urlparse(uri)
        scheme = (parsed.scheme or "").lower()
        host = parsed.hostname or ""

        if scheme in {"mailto", "tel", "sms"}:
            _open_external(uri)
            decision.ignore()
            return True

        user_link = nav_type == WebKit.NavigationType.LINK_CLICKED
        new_window = decision_type == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION
        if (user_link or new_window) and scheme in {"http", "https"} and host and not _is_internal(host):
            _open_external(uri)
            decision.ignore()
            return True
        return False

    def _on_create(self, view, action):
        try:
            request = action.get_request()
            uri = request.get_uri() or ""
        except Exception:
            uri = ""
        host = urlparse(uri).hostname or ""
        if uri.startswith("http") and host and not _is_internal(host):
            _open_external(uri)
            return None

        popup = WebKit.WebView(related_view=view)
        self._wire_view(popup)
        popup.connect("notify::uri", self._on_popup_uri)
        win = Adw.Window(transient_for=self, title="Google Messages")
        win.set_default_size(520, 720)
        win.set_content(popup)
        popup.connect("close", lambda *_: win.close())
        win.present()
        return popup

    def _on_popup_uri(self, view, *_args) -> None:
        uri = view.get_uri() or ""
        if "messages.google.com" in uri:
            window = view.get_root()
            if window is not None:
                window.close()
            self._view.load_uri(uri)
            self.reveal()
