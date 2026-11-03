// SPDX-License-Identifier: GPL-2.0-or-later

import Adw from 'gi://Adw';
import Gio from 'gi://Gio';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class ScreenshareDoctorPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({
            title: 'Command-line tool',
            description: 'The extension runs screenshare-doctor when you open its menu. Leave the path ' +
                'empty to use the one found in PATH or in ~/.local/bin.',
        });
        const path = new Adw.EntryRow({title: 'Path of screenshare-doctor'});
        settings.bind('cli-path', path, 'text', Gio.SettingsBindFlags.DEFAULT);
        group.add(path);
        page.add(group);
        window.add(page);
    }
}
