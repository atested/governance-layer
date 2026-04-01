async function loadPartial(targetId, path) {
  const target = document.getElementById(targetId);
  if (!target) return;

  try {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error(`Failed to load ${path}`);
    target.innerHTML = await res.text();
  } catch (err) {
    console.error(err);
  }
}

function markActiveLinks() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";

  document.querySelectorAll("[data-nav-link]").forEach(link => {
    const href = link.getAttribute("href")?.replace(/\/+$/, "") || "/";
    if (href === path) {
      link.classList.add("active");
    }
  });
}

function initMobileNav() {
  const toggle = document.getElementById("nav-toggle");
  const mobileNav = document.getElementById("mobile-nav");

  if (!toggle || !mobileNav) return;

  toggle.addEventListener("click", () => {
    const open = mobileNav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open);
  });
}

async function initSiteChrome() {
  await loadPartial("site-nav", "/partials/nav.html");
  await loadPartial("site-footer", "/partials/footer.html");

  markActiveLinks();
  initMobileNav();
}

window.addEventListener("DOMContentLoaded", initSiteChrome);
