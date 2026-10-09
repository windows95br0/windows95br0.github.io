"use strict";

document.documentElement.classList.add("js");

const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#main-nav");

function closeMenu() {
  menuButton.setAttribute("aria-expanded", "false");
  navigation.classList.remove("is-open");
}

menuButton.addEventListener("click", () => {
  const open = menuButton.getAttribute("aria-expanded") !== "true";
  menuButton.setAttribute("aria-expanded", String(open));
  navigation.classList.toggle("is-open", open);
});

navigation.addEventListener("click", (event) => {
  if (event.target.closest("a")) closeMenu();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menuButton.getAttribute("aria-expanded") === "true") {
    closeMenu();
    menuButton.focus();
  }
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".header-inner")) closeMenu();
});

window.matchMedia("(min-width: 641px)").addEventListener("change", closeMenu);

const filters = document.querySelectorAll("[data-filter]");
const activities = document.querySelectorAll("[data-category]");
const activityCount = document.querySelector(".activity-count");

filters.forEach((filter) => {
  filter.addEventListener("click", () => {
    const selected = filter.dataset.filter;
    filters.forEach((button) => {
      const active = button === filter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    let count = 0;
    activities.forEach((activity) => {
      const visible = selected === "all" || activity.dataset.category.split(" ").includes(selected);
      activity.hidden = !visible;
      if (visible) count += 1;
    });
    activityCount.textContent = `${count} ${count === 1 ? "way" : "ways"} to play`;
  });
});

document.querySelector("#copyright-year").textContent = String(new Date().getFullYear());
