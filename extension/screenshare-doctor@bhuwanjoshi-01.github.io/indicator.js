// SPDX-License-Identifier: GPL-2.0-or-later

import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {findCli, runCli} from './cli.js';
import {IDLE_ICON, parseReport, summarize} from './report.js';

const PROJECT_URI = 'https://github.com/BhuwanJoshi-01/screenshare-doctor';
const GUIDE_URI = `${PROJECT_URI}/blob/main/docs/troubleshooting.md`;
const INSTALL_COMMAND = 'uv tool install screenshare-doctor';

function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}

function logFailure(e) {
    console.error(`[screenshare-doctor] ${e.message}`);
}

export const DoctorIndicator = GObject.registerClass(
class DoctorIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, extension.metadata.name);
        this._settings = extension.getSettings();
        this._cancellable = new Gio.Cancellable();
        this._running = false;

        this._icon = new St.Icon({icon_name: IDLE_ICON, style_class: 'system-status-icon'});
        this.add_child(this._icon);

        this._header = new PopupMenu.PopupMenuItem('Open this menu to check screen sharing', {
            reactive: false,
            style_class: 'ssd-header',
        });
        this.menu.addMenuItem(this._header);
        this._context = new PopupMenu.PopupMenuItem('', {reactive: false, style_class: 'ssd-context'});
        this.menu.addMenuItem(this._context);
        this._problems = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._problems);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        // Shown when the tool is installed.
        this._actions = new PopupMenu.PopupMenuSection();
        this._actions.addAction('Check again', () => this._refresh());
        this._actions.addAction('Copy a report for a bug tracker', () => this._copyReport());
        this.menu.addMenuItem(this._actions);
        // Shown when it is not.
        this._install = new PopupMenu.PopupMenuSection();
        this._install.addAction(`Copy the install command (${INSTALL_COMMAND})`, () => {
            copyToClipboard(INSTALL_COMMAND);
        });
        this._install.addAction('Open the project page', () => {
            Gio.AppInfo.launch_default_for_uri_async(PROJECT_URI, null, null, null);
        });
        this._install.actor.visible = false;
        this.menu.addMenuItem(this._install);
        this.menu.addAction('Open the troubleshooting guide', () => {
            Gio.AppInfo.launch_default_for_uri_async(GUIDE_URI, null, null, null);
        });

        // The check runs only when someone opens the menu: never in the background.
        this.menu.connect('open-state-changed', (_menu, open) => {
            if (open)
                this._refresh();
        });
    }

    destroy() {
        this._cancellable.cancel();
        this._settings = null;
        super.destroy();
    }

    async _refresh() {
        if (this._running)
            return;
        const cli = findCli(this._settings.get_string('cli-path'));
        this._install.actor.visible = cli === null;
        this._actions.actor.visible = cli !== null;
        if (cli === null) {
            this._showError('screenshare-doctor is not installed');
            this._context.label.text = 'The extension shows what the command-line tool finds.';
            return;
        }
        this._running = true;
        this._header.label.text = 'Checking screen sharing…';
        let view;
        try {
            const output = await runCli(cli, ['doctor', '--format', 'json'], this._cancellable);
            view = summarize(parseReport(output));
        } catch (e) {
            if (!this._cancellable.is_cancelled()) {
                this._showError(`The check failed: ${e.message}`);
                logFailure(e);
            }
            return;
        } finally {
            this._running = false;
        }
        // the indicator may have been destroyed while the tool was running
        if (this._cancellable.is_cancelled())
            return;
        this._show(view);
    }

    // The Markdown report is redacted by the tool itself (home paths, names, secrets).
    async _copyReport() {
        const cli = findCli(this._settings.get_string('cli-path'));
        if (cli === null)
            return;
        this._header.label.text = 'Writing the report…';
        try {
            copyToClipboard(await runCli(cli, ['report'], this._cancellable));
            if (!this._cancellable.is_cancelled())
                this._header.label.text = 'Report copied; read it before you share it';
        } catch (e) {
            if (!this._cancellable.is_cancelled()) {
                this._header.label.text = `The report failed: ${e.message}`;
                logFailure(e);
            }
        }
    }

    _show(view) {
        this._icon.icon_name = view.icon;
        this._header.label.text = view.headline;
        this._context.label.text = [view.context, view.counts].filter(Boolean).join(' — ');
        this._problems.removeAll();
        for (const problem of view.problems) {
            const item = new PopupMenu.PopupMenuItem(`${problem.label}  ${problem.summary}`, {
                reactive: false,
                style_class: `ssd-problem ssd-${problem.status}`,
            });
            item.label.clutter_text.line_wrap = true;
            this._problems.addMenuItem(item);
            if (problem.next) {
                const next = new PopupMenu.PopupMenuItem(problem.next, {
                    reactive: false,
                    style_class: 'ssd-next',
                });
                next.label.clutter_text.line_wrap = true;
                this._problems.addMenuItem(next);
            }
        }
    }

    _showError(message) {
        this._icon.icon_name = 'dialog-question-symbolic';
        this._header.label.text = message;
        this._context.label.text = '';
        this._problems.removeAll();
    }
});
