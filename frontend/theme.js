// Light / dark switch shared by both pages. The choice is remembered in the browser.
// With no saved choice the page follows the computer's own light/dark setting.
(function () {
    const KEY = "theme";
    const root = document.documentElement;

    try {
        const saved = localStorage.getItem(KEY);
        if (saved === "dark" || saved === "light") root.dataset.theme = saved;
    } catch (error) { /* private mode: just follow the system setting */ }

    function current() {
        if (root.dataset.theme) return root.dataset.theme;
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function updateButton() {
        const button = document.getElementById("themeToggle");
        if (button) button.textContent = current() === "dark" ? "Switch to light mode" : "Switch to dark mode";
    }

    function choose(mode) {
        root.dataset.theme = mode;
        try { localStorage.setItem(KEY, mode); } catch (error) { /* ignore */ }
        updateButton();
        window.dispatchEvent(new CustomEvent("themechange", { detail: mode }));
    }

    window.currentTheme = current;

    document.addEventListener("DOMContentLoaded", () => {
        const button = document.getElementById("themeToggle");
        if (button) button.addEventListener("click", () => choose(current() === "dark" ? "light" : "dark"));
        updateButton();
    });

    if (window.matchMedia) {
        const query = window.matchMedia("(prefers-color-scheme: dark)");
        const onChange = () => {
            if (!root.dataset.theme) {
                updateButton();
                window.dispatchEvent(new CustomEvent("themechange"));
            }
        };
        if (query.addEventListener) query.addEventListener("change", onChange);
    }
})();
