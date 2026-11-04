// SPDX-License-Identifier: GPL-2.0-or-later

import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {findCli, isCancelled, runCli} from './cli.js';
import {IDLE_ICON, parseReport, summarize} from './report.js';

const PROJECT_URI = 'https://github.com/BhuwanJoshi-01/screenshare-doctor';
const GUIDE_URI = `${PROJECT_URI}/blob/main/docs/troubleshooting.md`;
const INSTALL_COMMAND = 'uv tool install screenshare-doctor';

function copyToClipboard(text) {
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
}

function openUri(uri) {
    Gio.AppInfo.launch_default_for_uri_async(uri, null, null, null);
}

export const DoctorIndicator = GObject.registerClass(
class DoctorIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, extension.metadata.name);
        this._settings = extension.getSettings();
        this._cancellable = new Gio.Cancellable();
        this._check = null;

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
        this._toolActions = new PopupMenu.PopupMenuSection();
        this._toolActions.addAction('Check again', () => this._refresh());
        this._toolActions.addAction('Copy a report for a bug tracker', () => this._copyReport());
        this.menu.addMenuItem(this._toolActions);
        this._installActions = new PopupMenu.PopupMenuSection();
        this._installActions.addAction(`Copy the install command (${INSTALL_COMMAND})`,
            () => copyToClipboard(INSTALL_COMMAND));
        this._installActions.addAction('Open the project page', () => openUri(PROJECT_URI));
        this._installActions.actor.visible = false;
        this.menu.addMenuItem(this._installActions);
        this.menu.addAction('Open the troubleshooting guide', () => openUri(GUIDE_URI));

        this.menu.connectObject('open-state-changed', (_menu, open) => {
            if (open)
                this._refresh();
        }, this);
    }

    destroy() {
        this._cancellable.cancel();
        this._cancellable = null;
        this._settings = null;
        super.destroy();
    }

    _cliPath() {
        return findCli(this._settings.get_string('cli-path'));
    }

    _refresh() {
        this._check ??= this._runCheck().finally(() => {
            this._check = null;
        });
    }

    async _runCheck() {
        const cli = this._cliPath();
        this._installActions.actor.visible = cli === null;
        this._toolActions.actor.visible = cli !== null;
        if (cli === null) {
            this._showError('screenshare-doctor is not installed');
            this._context.label.text = 'The extension shows what the command-line tool finds.';
            return;
        }
        this._header.label.text = 'Checking screen sharing…';
        try {
            const output = await runCli(cli, ['doctor', '--format', 'json'], this._cancellable);
            this._show(summarize(parseReport(output)));
        } catch (e) {
            this._reportFailure('The check failed', e, message => this._showError(message));
        }
    }

    async _copyReport() {
        const cli = this._cliPath();
        if (cli === null)
            return;
        this._header.label.text = 'Writing the report…';
        try {
            copyToClipboard(await runCli(cli, ['report'], this._cancellable));
            this._header.label.text = 'Report copied; read it before you share it';
        } catch (e) {
            this._reportFailure('The report failed', e, message => {
                this._header.label.text = message;
            });
        }
    }

    _reportFailure(what, error, show) {
        if (isCancelled(error))
            return;
        show(`${what}: ${error.message}`);
        console.error(`[screenshare-doctor] ${error.message}`);
    }

    _show(view) {
        this._icon.icon_name = view.icon;
        this._header.label.text = view.headline;
        this._context.label.text = [view.context, view.counts].filter(Boolean).join(' — ');
        this._problems.removeAll();
        for (const problem of view.problems) {
            this._addProblemLine(`${problem.label}  ${problem.summary}`, `ssd-problem ssd-${problem.status}`);
            if (problem.next)
                this._addProblemLine(problem.next, 'ssd-next');
        }
    }

    _addProblemLine(text, styleClass) {
        const item = new PopupMenu.PopupMenuItem(text, {reactive: false, style_class: styleClass});
        item.label.clutter_text.line_wrap = true;
        this._problems.addMenuItem(item);
    }

    _showError(message) {
        this._icon.icon_name = 'dialog-question-symbolic';
        this._header.label.text = message;
        this._context.label.text = '';
        this._problems.removeAll();
    }
});
