// Screenshare Doctor project page: the signal path of "Follow the signal" and the copy button.
// SPDX-License-Identifier: MIT
//
// The symptoms, their checks in order and the desktop defaults are copied from
// src/screenshare_doctor/troubleshoot/symptoms.json and bundles/desktops.json.

"use strict";

const CHECKS = {
    "SSD-SESSION-001": ["session", "The desktop session is Wayland"],
    "SSD-SESSION-002": ["session", "Apps started here can reach the Wayland display"],
    "SSD-SESSION-003": ["session", "The portal knows which desktop this is"],
    "SSD-SESSION-004": ["session", "Portals see the session's display variables"],
    "SSD-DBUS-001": ["session", "The session bus answers"],
    "SSD-PKG-001": ["portal-frontend", "xdg-desktop-portal is installed"],
    "SSD-SERVICE-001": ["portal-frontend", "The portal's user service is not failed or masked"],
    "SSD-PORTAL-001": ["portal-frontend", "The portal frontend offers ScreenCast"],
    "SSD-PORTAL-002": ["portal-backend", "ScreenCast has a backend that can answer"],
    "SSD-PORTAL-003": ["portal-frontend", "The portal reads the configuration as intended"],
    "SSD-PORTAL-004": ["portal-backend", "Single windows can be shared"],
    "SSD-DESKTOP-001": ["portal-backend", "The setup matches the desktop's defaults"],
    "SSD-COMPOSITOR-001": ["compositor", "The compositor offers screen casts"],
    "SSD-PW-001": ["pipewire", "PipeWire can carry the screen cast"],
    "SSD-WP-001": ["wireplumber", "WirePlumber manages the PipeWire graph"],
};

const SYMPTOMS = [
    {
        id: "no-picker",
        label: "No picker",
        title: "Clicking Share shows no screen or window picker",
        why: "The picker is drawn by the portal backend, so when it never appears the request did not get that far: the portal is not reachable, cannot start, has no backend for ScreenCast, or the backend cannot reach the compositor.",
        checks: ["SSD-SESSION-004", "SSD-SESSION-003", "SSD-DBUS-001", "SSD-PKG-001", "SSD-SERVICE-001", "SSD-PORTAL-001", "SSD-PORTAL-002", "SSD-PORTAL-003", "SSD-DESKTOP-001", "SSD-COMPOSITOR-001"],
    },
    {
        id: "black-screen",
        label: "Black screen",
        title: "The picker works, but viewers see a black or frozen frame",
        why: "Choosing a screen worked, so the portal and its backend answered; the frame travels from the compositor through PipeWire to the app, and one of those links is missing or the app reads it the wrong way.",
        checks: ["SSD-COMPOSITOR-001", "SSD-PW-001", "SSD-WP-001", "SSD-PORTAL-002", "SSD-SESSION-002", "SSD-DESKTOP-001"],
    },
    {
        id: "missing-window",
        label: "A window is missing",
        title: "The window I want is not offered",
        why: "The list of windows comes from the portal backend and the compositor. Some backends offer whole screens only, and apps running through XWayland may only see X11 windows.",
        checks: ["SSD-PORTAL-004", "SSD-PORTAL-002", "SSD-DESKTOP-001", "SSD-SESSION-002"],
    },
    {
        id: "permission-denied",
        label: "Permission denied",
        title: "The app says screen sharing was denied or is not allowed",
        why: "A denial comes from the portal: the request was cancelled, the backend refused it, or no backend answered and the app reports that as a denial.",
        checks: ["SSD-PORTAL-001", "SSD-PORTAL-002", "SSD-SESSION-004", "SSD-DESKTOP-001"],
    },
    {
        id: "app-only",
        label: "Only some apps",
        title: "Only some apps' windows can be shared",
        why: "On Wayland every window is offered by the compositor through the portal; an app that only lists some windows usually runs through XWayland and looks for X11 windows itself.",
        checks: ["SSD-SESSION-002", "SSD-PORTAL-004", "SSD-PORTAL-002"],
    },
];

const DESKTOPS = [
    {
        id: "gnome", label: "GNOME", backend: "gnome", package: "xdg-desktop-portal-gnome",
        config: "gnome-portals.conf", defaults: "gnome;gtk", shippedBy: "gnome-session",
        compositor: "Mutter", compositorNote: "org.gnome.Mutter.ScreenCast must run on the session bus",
    },
    {
        id: "kde", label: "KDE Plasma", backend: "kde", package: "xdg-desktop-portal-kde",
        config: "kde-portals.conf", defaults: "kde", shippedBy: "plasma-workspace",
        compositor: "KWin", compositorNote: null,
    },
    {
        id: "hyprland", label: "Hyprland", backend: "hyprland", package: "xdg-desktop-portal-hyprland",
        config: "hyprland-portals.conf", defaults: "hyprland;gtk", shippedBy: "Hyprland",
        compositor: "Hyprland", compositorNote: null,
    },
];

const LAYER_ORDER = ["session", "portal-frontend", "portal-backend", "compositor", "pipewire", "wireplumber"];

function note(code, desktop) {
    switch (code) {
    case "SSD-PORTAL-002":
        return `Expected: the ${desktop.backend} backend, from ${desktop.config} (default=${desktop.defaults}).`;
    case "SSD-DESKTOP-001":
        return `${desktop.package} installed, ${desktop.config} from ${desktop.shippedBy} readable.`;
    case "SSD-COMPOSITOR-001":
        return desktop.compositorNote
            ? `${desktop.compositor}: ${desktop.compositorNote}.`
            : `Not applicable: ${desktop.compositor} offers screen casts through Wayland protocols.`;
    case "SSD-PORTAL-004":
        return `Whether the ${desktop.backend} backend offers windows, not only whole screens.`;
    case "SSD-SESSION-003":
        return `XDG_CURRENT_DESKTOP should name ${desktop.label}, as the user manager sees it.`;
    case "SSD-PW-001":
        return "Running, or starting on demand through pipewire.socket; never started to ask.";
    default:
        return "";
    }
}

const state = { symptom: "black-screen", desktop: "gnome" };

function chips(group, items) {
    const row = document.querySelector(`[data-group="${group}"]`);
    for (const item of items) {
        const label = document.createElement("label");
        label.className = "chip";
        const input = document.createElement("input");
        input.type = "radio";
        input.name = group;
        input.value = item.id;
        input.checked = state[group] === item.id;
        input.addEventListener("change", () => {
            state[group] = item.id;
            render();
        });
        const text = document.createElement("span");
        text.textContent = item.label;
        label.append(input, text);
        row.append(label);
    }
}

function field(name) {
    return document.querySelector(`[data-field="${name}"]`);
}

function render() {
    const symptom = SYMPTOMS.find((s) => s.id === state.symptom);
    const desktop = DESKTOPS.find((d) => d.id === state.desktop);

    field("backend").textContent = desktop.package;
    field("compositor").textContent = desktop.compositor;

    const first = new Map();
    symptom.checks.forEach((code, index) => {
        const layer = CHECKS[code][0];
        if (!first.has(layer)) first.set(layer, index);
    });
    const ranked = LAYER_ORDER.filter((layer) => first.has(layer))
        .sort((a, b) => first.get(a) - first.get(b));
    for (const node of document.querySelectorAll(".path li")) {
        const position = ranked.indexOf(node.dataset.layer);
        if (position >= 0) node.dataset.order = String(position + 1);
        else delete node.dataset.order;
    }

    field("symptom-title").textContent = symptom.title;
    field("symptom-why").textContent = symptom.why;
    const list = field("checks");
    list.replaceChildren(...symptom.checks.map((code) => {
        const item = document.createElement("li");
        const id = document.createElement("code");
        id.textContent = code;
        const what = document.createElement("span");
        what.className = "what";
        what.textContent = CHECKS[code][1];
        const detail = note(code, desktop);
        if (detail) {
            const small = document.createElement("span");
            small.className = "note";
            small.textContent = detail;
            what.append(small);
        }
        item.append(id, what);
        return item;
    }));
    field("command").textContent =
        `screenshare-doctor troubleshoot screenshare --app firefox --symptom ${symptom.id}`;
}

chips("symptom", SYMPTOMS);
chips("desktop", DESKTOPS);
render();

for (const button of document.querySelectorAll("[data-copy]")) {
    button.addEventListener("click", async () => {
        const text = document.getElementById(button.dataset.copy).textContent;
        try {
            await navigator.clipboard.writeText(text);
            button.textContent = "Copied";
            button.dataset.state = "done";
        } catch {
            button.textContent = "Select and copy";
        }
        setTimeout(() => {
            button.textContent = "Copy";
            delete button.dataset.state;
        }, 2000);
    });
}
