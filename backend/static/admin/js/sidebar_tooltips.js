// Adds a hoverable "?" to each sidebar entry, explaining what that screen is
// for. Descriptions are supplied by templates/admin/base_site.html and keyed
// by "<app>/<model>" -- keying by app alone gave every model in an app the
// same label.
document.addEventListener("DOMContentLoaded", function () {
    const descriptions = window.JAZZMIN_SIDEBAR_DESCRIPTIONS || {};

    document.querySelectorAll(".sidebar .nav-link").forEach(function (link) {
        const href = link.getAttribute("href");
        if (!href) {
            return;
        }

        const parts = href.split("/").filter(Boolean);
        if (parts.length < 3) {
            return;
        }

        // Custom links sit deeper than "<app>/<model>/", so try the last
        // segment before falling back to the model name.
        const app = parts[1];
        const description =
            descriptions[app + "/" + parts[parts.length - 1]] ||
            descriptions[app + "/" + parts[2]];
        if (!description) {
            return;
        }

        const icon = document.createElement("span");
        icon.textContent = "?";
        icon.className = "sidebar-tooltip-icon";
        icon.title = description;
        icon.setAttribute("data-bs-toggle", "tooltip");
        link.appendChild(icon);
    });

    if (typeof bootstrap !== "undefined") {
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            new bootstrap.Tooltip(el, { placement: "right" });
        });
    }
});
