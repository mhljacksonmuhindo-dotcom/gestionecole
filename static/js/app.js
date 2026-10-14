document.addEventListener("DOMContentLoaded", function () {
  const menuToggle = document.getElementById("menuToggle");
  const sidebar = document.getElementById("sidebar");
  const currentDate =
    document.getElementById("todayDate") ||
    document.getElementById("currentDate");

  if (currentDate) {
    currentDate.textContent = new Intl.DateTimeFormat("fr-FR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    }).format(new Date());
  }

  if (menuToggle && sidebar) {
    menuToggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });

    document.addEventListener("click", function (event) {
      const clickedInsideSidebar = sidebar.contains(event.target);
      const clickedToggle = menuToggle.contains(event.target);

      if (window.innerWidth <= 760 && !clickedInsideSidebar && !clickedToggle) {
        sidebar.classList.remove("open");
      }
    });
  }

  const currentPath = window.location.pathname;
  document.querySelectorAll(".nav-link").forEach(function (link) {
    if (link.pathname === currentPath) {
      link.classList.add("active");
    }
  });
});
