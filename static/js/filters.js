(function () {
  function getFilterValues() {
    const fields = document.querySelectorAll("[data-filter]");
    const values = {};

    fields.forEach((field) => {
      const key = field.getAttribute("data-filter");
      values[key] = field.value;
    });

    return values;
  }

  function applyFilters() {
    const values = getFilterValues();
    window.dispatchEvent(new CustomEvent("mediflow:filters:apply", { detail: values }));
  }

  function resetFilters() {
    document.querySelectorAll("[data-filter]").forEach((field) => {
      field.value = "";
    });
    applyFilters();
  }

  document.addEventListener("click", function (event) {
    const target = event.target.closest("[data-action]");
    if (!target) return;

    const action = target.getAttribute("data-action");
    if (action === "apply-filters") applyFilters();
    if (action === "reset-filters") resetFilters();
  });
})();
