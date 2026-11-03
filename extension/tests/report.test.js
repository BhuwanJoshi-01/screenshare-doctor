// SPDX-License-Identifier: GPL-2.0-or-later
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';

import {
    IDLE_ICON, iconFor, parseReport, summarize,
} from '../screenshare-doctor@bhuwanjoshi-01.github.io/report.js';

const healthy = readFileSync(new URL('./healthy.json', import.meta.url), 'utf8');

function finding(id, status, extra = {}) {
    return {id, status, summary: `${id} summary`, recommended_action: null, caused_by: null, ...extra};
}

function report(findings, worst) {
    return {schema_version: 1, summary: {session: 'wayland', desktop_name: 'gnome', worst, counts: {}}, findings};
}

test('the real healthy report says screen sharing should work', () => {
    const view = summarize(parseReport(healthy));
    assert.equal(view.icon, 'screen-shared-symbolic');
    assert.equal(view.headline, 'Screen sharing should work (15 checks pass)');
    assert.equal(view.context, 'Wayland · gnome');
    assert.equal(view.counts, '15 pass');
    assert.deepEqual(view.problems, []);
});

test('a failure sets the icon and the headline', () => {
    const view = summarize(report([
        finding('SSD-PORTAL-002', 'fail', {recommended_action: 'Install the backend.'}),
        finding('SSD-PW-001', 'pass'),
    ], 'fail'));
    assert.equal(view.icon, 'dialog-error-symbolic');
    assert.equal(view.headline, 'Screen sharing will not work: 1 problem(s)');
    assert.deepEqual(view.problems, [{
        id: 'SSD-PORTAL-002', status: 'fail', label: 'FAIL',
        summary: 'SSD-PORTAL-002 summary', next: 'Install the backend.',
    }]);
});

test('findings that follow from a reported root cause are folded', () => {
    const view = summarize(report([
        finding('SSD-DBUS-001', 'fail'),
        finding('SSD-PORTAL-001', 'unknown', {caused_by: 'SSD-DBUS-001'}),
        finding('SSD-PORTAL-002', 'unknown', {caused_by: 'SSD-OTHER-001'}),
    ], 'fail'));
    assert.deepEqual(view.problems.map(p => p.id), ['SSD-DBUS-001', 'SSD-PORTAL-002']);
});

test('warnings say "may not work"', () => {
    const view = summarize(report([finding('SSD-PORTAL-004', 'warn')], 'warn'));
    assert.equal(view.icon, 'dialog-warning-symbolic');
    assert.match(view.headline, /^Screen sharing may not work/);
});

test('icons for every status, and the idle icon', () => {
    assert.equal(iconFor('unknown'), 'dialog-question-symbolic');
    assert.equal(iconFor(null), IDLE_ICON);
    assert.equal(iconFor('not_applicable'), IDLE_ICON);
});

test('output that is not a report is rejected with a readable message', () => {
    assert.throws(() => parseReport('Traceback (most recent call last):'), /did not print a JSON report/);
    assert.throws(() => parseReport('[]'), /did not print a JSON report/);
    assert.throws(() => parseReport('{"schema_version": 2}'), /format 2 is not supported/);
    assert.throws(() => parseReport('{"schema_version": 1}'), /no findings/);
});
