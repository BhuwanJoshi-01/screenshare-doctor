// SPDX-License-Identifier: GPL-2.0-or-later
//
// Runs the screenshare-doctor command-line tool, asynchronously and bounded: the
// shell never waits for it, a cancelled run is killed, and a run that takes longer
// than TIMEOUT_SECONDS is killed too. The timeout is the only main-loop source; it
// is removed as soon as the run ends or is cancelled.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export const TIMEOUT_SECONDS = 60;

/** The tool's path: the configured one, else from PATH, else ~/.local/bin; null if none. */
export function findCli(configured) {
    if (configured)
        return GLib.file_test(configured, GLib.FileTest.IS_EXECUTABLE) ? configured : null;
    const inPath = GLib.find_program_in_path('screenshare-doctor');
    if (inPath)
        return inPath;
    const local = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'screenshare-doctor']);
    return GLib.file_test(local, GLib.FileTest.IS_EXECUTABLE) ? local : null;
}

/** Whether a run was rejected because its cancellable was cancelled. */
export function isCancelled(error) {
    return error instanceof GLib.Error && error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED);
}

/**
 * Resolves to the tool's standard output; rejects with a readable Error, or with the
 * cancellation error when `cancellable` is cancelled.
 */
export function runCli(path, args, cancellable, timeoutSeconds = TIMEOUT_SECONDS) {
    return new Promise((resolve, reject) => {
        const proc = Gio.Subprocess.new([path, ...args],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
        let timedOut = false;
        let timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, timeoutSeconds, () => {
            timedOut = true;
            timeoutId = 0;
            proc.force_exit();
            return GLib.SOURCE_REMOVE;
        });
        const removeTimeout = () => {
            if (timeoutId) {
                GLib.Source.remove(timeoutId);
                timeoutId = 0;
            }
        };
        // Cancelling (disable() does) removes the timeout at once and kills the child.
        const cancelId = cancellable.connect(() => {
            removeTimeout();
            proc.force_exit();
        });
        proc.communicate_utf8_async(null, cancellable, (p, res) => {
            removeTimeout();
            cancellable.disconnect(cancelId);
            try {
                const [, stdout, stderr] = p.communicate_utf8_finish(res);
                if (timedOut)
                    reject(new Error(`no answer within ${timeoutSeconds} s`));
                else if (p.get_successful())
                    resolve(stdout);
                else
                    reject(new Error(stderr.trim().split('\n').pop() || `exit status ${p.get_exit_status()}`));
            } catch (e) {
                reject(timedOut ? new Error(`no answer within ${timeoutSeconds} s`) : e);
            }
        });
    });
}
