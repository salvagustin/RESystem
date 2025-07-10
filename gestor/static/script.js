document.addEventListener("DOMContentLoaded", function () {
    const toggleButton = document.getElementById("toggleDarkMode");
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const icon = toggleButton.querySelector("i");
    icon.classList.toggle("bi-moon-fill", !document.body.classList.contains("dark-mode"));
    icon.classList.toggle("bi-sun-fill", document.body.classList.contains("dark-mode"));

    // Guardar en localStorage
    if (localStorage.getItem('theme') === 'dark' || (prefersDark && !localStorage.getItem('theme'))) {
        document.body.classList.add('dark-mode');
    }

    toggleButton.addEventListener("click", () => {
        document.body.classList.toggle("dark-mode");
        localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
    });
});