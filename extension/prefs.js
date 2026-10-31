// SPDX-License-Identifier: GPL-3.0-or-later

import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class GoogleMessagesPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({
            title: 'Google Messages',
            description: 'The helper window uses Messages for web. Your phone must stay on and connected.',
        });

        const account = new Adw.EntryRow({
            title: 'Google account',
            text: settings.get_string('google-account'),
        });
        account.connect('changed', row => {
            settings.set_string('google-account', row.get_text().trim() || 'juanton@wahcha.com');
        });
        group.add(account);

        const hidden = new Adw.SwitchRow({
            title: 'Start in the background',
            subtitle: 'Open the window with a left-click on the top-bar icon',
            active: settings.get_boolean('start-hidden'),
        });
        hidden.connect('notify::active', row => {
            settings.set_boolean('start-hidden', row.active);
        });
        group.add(hidden);

        const note = new Gtk.Label({
            label: 'Left-click the top-bar icon to show or hide Messages. Right-click opens the menu.',
            wrap: true,
            xalign: 0,
            margin_top: 8,
        });
        note.add_css_class('dim-label');
        group.add(note);

        page.add(group);
        window.add(page);
        window.set_title('Google Messages');
        window.set_default_size(480, 280);
    }
}
