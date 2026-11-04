// SPDX-License-Identifier: GPL-2.0-or-later
//
// gjs -m extension/tests/cli.gjs.js
// Runs cli.js under GJS against small stand-in programs: a normal run, a failing
// one, a cancelled one and one that never ends (killed by the timeout).

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import System from 'system';

import {findCli, isCancelled, runCli} from '../screenshare-doctor@bhuwanjoshi-01.github.io/cli.js';

const dir = GLib.dir_make_tmp('ssd-cli-XXXXXX');

function program(name, body) {
    const path = GLib.build_filenamev([dir, name]);
    GLib.file_set_contents(path, `#!/bin/sh\n${body}\n`);
    GLib.chmod(path, 0o755);
    return path;
}

const ok = program('ok', 'echo "$@"');
const fails = program('fails', 'echo first >&2; echo "screenshare-doctor: internal error" >&2; exit 2');
const hangs = program('hangs', 'exec sleep 30');
let failures = 0;

async function check(name, run) {
    try {
        await run();
        print(`ok - ${name}`);
    } catch (e) {
        failures++;
        print(`not ok - ${name}: ${e.message}`);
    }
}

function assert(condition, message) {
    if (!condition)
        throw new Error(message);
}

async function main() {
    await check('a run resolves to standard output', async () => {
        const out = await runCli(ok, ['doctor', '--format', 'json'], new Gio.Cancellable());
        assert(out === 'doctor --format json\n', `got ${JSON.stringify(out)}`);
    });
    await check('a failing run rejects with the last line of stderr', async () => {
        let message = null;
        await runCli(fails, [], new Gio.Cancellable()).catch(e => (message = e.message));
        assert(message === 'screenshare-doctor: internal error', `got ${message}`);
    });
    await check('a run that never ends is killed by the timeout', async () => {
        const start = GLib.get_monotonic_time();
        let message = null;
        await runCli(hangs, [], new Gio.Cancellable(), 1).catch(e => (message = e.message));
        const seconds = (GLib.get_monotonic_time() - start) / 1e6;
        assert(message === 'no answer within 1 s', `got ${message}`);
        assert(seconds < 5, `took ${seconds} s`);
    });
    await check('cancelling kills the running program', async () => {
        const cancellable = new Gio.Cancellable();
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
            cancellable.cancel();
            return GLib.SOURCE_REMOVE;
        });
        const start = GLib.get_monotonic_time();
        let error = null;
        await runCli(hangs, [], cancellable, 30).catch(e => (error = e));
        assert(error !== null, 'did not reject');
        assert(isCancelled(error), `rejected with ${error} instead of the cancellation`);
        assert((GLib.get_monotonic_time() - start) / 1e6 < 5, 'was not killed');
    });
    await check('a program that cannot start rejects', async () => {
        let error = null;
        await runCli(GLib.build_filenamev([dir, 'missing']), [], new Gio.Cancellable()).catch(e => (error = e));
        assert(error !== null, 'did not reject');
        assert(!isCancelled(error), 'reported a failed start as a cancellation');
    });
    await check('a failure is not a cancellation', async () => {
        let error = null;
        await runCli(fails, [], new Gio.Cancellable()).catch(e => (error = e));
        assert(error !== null && !isCancelled(error), 'a failed run looked cancelled');
    });
    await check('a missing configured path is not found', async () => {
        assert(findCli(GLib.build_filenamev([dir, 'missing'])) === null, 'found a missing file');
        assert(findCli(ok) === ok, 'did not accept an executable');
    });
}

const loop = new GLib.MainLoop(null, false);
main().finally(() => loop.quit());
loop.run();
for (const name of ['ok', 'fails', 'hangs'])
    GLib.unlink(GLib.build_filenamev([dir, name]));
GLib.rmdir(dir);
if (failures)
    System.exit(1);
