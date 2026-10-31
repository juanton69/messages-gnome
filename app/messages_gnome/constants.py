from __future__ import annotations

from urllib.parse import urlencode

from messages_gnome import DEFAULT_GOOGLE_ACCOUNT

CONVERSATIONS_URL = "https://messages.google.com/web/conversations"
AUTHENTICATION_URL = "https://messages.google.com/web/authentication"
DEFAULT_START_URL = CONVERSATIONS_URL
DEFAULT_ACCOUNT = DEFAULT_GOOGLE_ACCOUNT

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Chrome/131.0.0.0 Safari/605.1.15"
)

INTERNAL_HOST_SUFFIXES = (
    "messages.google.com",
    "accounts.google.com",
    "accounts.youtube.com",
    "myaccount.google.com",
    "googleapis.com",
    "gstatic.com",
    "googleusercontent.com",
    "ggpht.com",
    "gvt1.com",
    "gvt2.com",
    "recaptcha.net",
    "g.co",
    "google.com",
)

EXTERNAL_HOST_SUFFIXES = (
    "support.google.com",
    "www.google.com",
    "youtube.com",
    "youtu.be",
    "maps.google.com",
    "mail.google.com",
    "drive.google.com",
    "docs.google.com",
    "photos.google.com",
    "calendar.google.com",
    "meet.google.com",
    "play.google.com",
)

INTROSPECTION_XML = """
<node>
  <interface name="org.juanton.MessagesGnome">
    <method name="Toggle"/>
    <method name="Show"/>
    <method name="Hide"/>
    <method name="Reload"/>
    <method name="Quit"/>
    <signal name="UnreadChanged">
      <arg type="i" name="count"/>
    </signal>
    <property name="Visible" type="b" access="read"/>
    <property name="UnreadCount" type="i" access="read"/>
  </interface>
</node>
"""


def account_chooser_url(email: str = DEFAULT_ACCOUNT, continue_url: str = CONVERSATIONS_URL) -> str:
    return "https://accounts.google.com/AccountChooser?" + urlencode(
        {
            "Email": email,
            "continue": continue_url,
            "hl": "en",
        }
    )


LOGIN_HINT_JS = r"""
(function (email) {
  if (!email) return;
  const wanted = String(email).trim().toLowerCase();
  const identified = Array.from(document.querySelectorAll("[data-identifier], [data-email]"));
  for (const node of identified) {
    const id = (node.getAttribute("data-identifier") || node.getAttribute("data-email") || "").toLowerCase();
    if (id === wanted) { node.click(); return; }
  }
  const input = document.querySelector("#identifierId")
    || document.querySelector("input[type='email']")
    || document.querySelector("input[name='identifier']");
  if (!input) return;
  if ((input.value || "").toLowerCase() === wanted) return;
  const proto = window.HTMLInputElement && window.HTMLInputElement.prototype;
  const desc = proto && Object.getOwnPropertyDescriptor(proto, "value");
  if (desc && desc.set) desc.set.call(input, email);
  else input.value = email;
  input.dispatchEvent(new Event("input", { bubbles: true }));
})(%EMAIL%);
"""

UNREAD_COUNT_JS = r"""
(() => {
  try {
    const titled = (document.title || "").match(/^\((\d+)\)/);
    if (titled) return parseInt(titled[1], 10);
    return document.querySelectorAll('[aria-label*="unread" i]').length;
  } catch (e) {
    return 0;
  }
})()
"""
