// SPDX-License-Identifier: GPL-2.0-or-later
//
// Turns the JSON of `screenshare-doctor doctor --format json` (schema version 1,
// docs/json-schema-v1.json) into what the menu shows. No GNOME imports, so the
// logic can be tested on its own.

export const SCHEMA_VERSION = 1;

const ICONS = {
    pass: 'screen-shared-symbolic',
    warn: 'dialog-warning-symbolic',
    fail: 'dialog-error-symbolic',
    unknown: 'dialog-question-symbolic',
};

export const IDLE_ICON = 'video-display-symbolic';

const PROBLEMS = ['fail', 'warn', 'unknown'];

const LABELS = {
    pass: 'PASS',
    warn: 'WARN',
    fail: 'FAIL',
    unknown: 'UNKNOWN',
    not_applicable: 'N/A',
    not_tested: 'NOT TESTED',
};

/** The icon for the worst status of a report; the idle icon when nothing ran. */
export function iconFor(worst) {
    return ICONS[worst] ?? IDLE_ICON;
}

/**
 * Parse the tool's output. Throws an Error with a readable message when it is not
 * a report this version understands.
 */
export function parseReport(text) {
    let document;
    try {
        document = JSON.parse(text);
    } catch {
        throw new Error('screenshare-doctor did not print a JSON report');
    }
    if (document === null || typeof document !== 'object' || Array.isArray(document))
        throw new Error('screenshare-doctor did not print a JSON report');
    if (document.schema_version !== SCHEMA_VERSION)
        throw new Error(`report format ${document.schema_version} is not supported; update the extension`);
    if (!Array.isArray(document.findings) || typeof document.summary !== 'object' || document.summary === null)
        throw new Error('the report has no findings');
    return document;
}

/**
 * What the menu shows: the headline, the icon, and the problems in report order,
 * without those that follow from another reported problem (their root cause is
 * shown instead).
 */
export function summarize(document) {
    const summary = document.summary;
    const counts = summary.counts ?? {};
    const reported = new Set(document.findings.map(f => f.id));
    const problems = document.findings
        .filter(f => PROBLEMS.includes(f.status))
        .filter(f => !f.caused_by || !reported.has(f.caused_by))
        .map(f => ({
            id: f.id,
            status: f.status,
            label: LABELS[f.status] ?? f.status,
            summary: f.summary,
            next: f.recommended_action ?? null,
        }));
    const parts = [];
    if (summary.session)
        parts.push(summary.session === 'wayland' ? 'Wayland' : summary.session);
    if (summary.desktop_name)
        parts.push(summary.desktop_name);
    const counted = ['pass', 'warn', 'fail', 'unknown']
        .filter(status => counts[status])
        .map(status => `${counts[status]} ${status}`);
    let headline;
    if (problems.length === 0)
        headline = `Screen sharing should work (${counts.pass ?? 0} checks pass)`;
    else if (summary.worst === 'fail')
        headline = `Screen sharing will not work: ${problems.length} problem(s)`;
    else
        headline = `Screen sharing may not work: ${problems.length} problem(s)`;
    return {
        icon: iconFor(summary.worst),
        headline,
        context: parts.join(' · '),
        counts: counted.join(', '),
        problems,
    };
}
