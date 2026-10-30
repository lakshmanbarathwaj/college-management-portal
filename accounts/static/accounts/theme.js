(() => {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;

  const updateToggle = () => {
    const isDark = root.dataset.theme === "dark";
    toggle.setAttribute("aria-pressed", String(isDark));
    toggle.setAttribute(
      "aria-label",
      isDark ? "Switch to light mode" : "Switch to dark mode",
    );
    toggle.querySelector(".theme-toggle-label").textContent = isDark
      ? "Light mode"
      : "Dark mode";
  };

  updateToggle();
  toggle.addEventListener("click", () => {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = nextTheme;
    try {
      localStorage.setItem("sembon.theme", nextTheme);
      toggle.removeAttribute("title");
    } catch (error) {
      toggle.title = "This theme choice could not be saved in your browser.";
      console.error("The appearance preference could not be saved.", error);
    }
    updateToggle();
  });
})();
