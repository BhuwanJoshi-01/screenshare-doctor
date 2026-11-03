// Screenshare Doctor - GNOME Shell extension
// SPDX-License-Identifier: GPL-2.0-or-later
//
// A top-bar indicator for the screenshare-doctor command-line tool. The tool does
// all the checking; this extension runs it when the menu is opened and shows the
// result. It never polls and never runs anything while the menu is closed.

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {DoctorIndicator} from './indicator.js';

export default class ScreenshareDoctorExtension extends Extension {
    enable() {
        this._indicator = new DoctorIndicator(this);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator.destroy();
        this._indicator = null;
    }
}
