(function () {
  window.MediFlowCharts = {
    mountBarChart: function (elementId, data) {
      const el = document.getElementById(elementId);
      if (!el) return;
      el.textContent = "Bar chart placeholder";
      el.dataset.points = String((data || []).length);
    },
    mountLineChart: function (elementId, data) {
      const el = document.getElementById(elementId);
      if (!el) return;
      el.textContent = "Line chart placeholder";
      el.dataset.points = String((data || []).length);
    }
  };
})();
