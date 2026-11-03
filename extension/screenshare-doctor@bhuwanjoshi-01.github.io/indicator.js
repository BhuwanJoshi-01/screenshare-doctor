// SPDX-License-Identifier: GPL-2.0-or-later

import GObject from 'gi://GObject';
import St from 'gi://St';

import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

export const DoctorIndicator = GObject.registerClass(
class DoctorIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, extension.metadata.name);
        this._extension = extension;
        this._icon = new St.Icon({
            icon_name: 'video-display-symbolic',
            style_class: 'system-status-icon',
        });
        this.add_child(this._icon);

        this._header = new PopupMenu.PopupMenuItem('Screen sharing not checked yet', {
            reactive: false,
        });
        this.menu.addMenuItem(this._header);
    }
});
