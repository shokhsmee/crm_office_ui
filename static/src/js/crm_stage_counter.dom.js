/** @odoo-module **/

(function safeCRMStageCounter() {
    // defensive wrapper to avoid breaking Discuss / backend
    try {
      function refreshKanbanCounts() {
        const columns = document.querySelectorAll(".o_kanban_group");
        if (!columns.length) return;
  
        columns.forEach((col) => {
          const counter = col.querySelector(".o_kanban_counter");
          if (!counter) return;
  
          // hide default zeros
          counter.querySelectorAll(".o_animated_number").forEach(
            (el) => (el.style.display = "none")
          );
  
          // count visible cards in that column
          const count = col.querySelectorAll(".o_kanban_record").length;
  
          let badge = counter.querySelector(".o_stage_real_count");
          if (!badge) {
            badge = document.createElement("div");
            badge.className = "o_stage_real_count ms-2 text-900 text-nowrap";
            counter.appendChild(badge);
          }
          badge.textContent = String(count);
          badge.title = "Lead count";
        });
      }
  
      function init() {
        // run once after load
        refreshKanbanCounts();
        // re-run when DOM changes (filters, drag-drops, reloads)
        const observer = new MutationObserver(refreshKanbanCounts);
        observer.observe(document.body, { childList: true, subtree: true });
        // manual refresh hook
        window.__crmRefreshStageCounts = refreshKanbanCounts;
      }
  
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
      } else {
        init();
      }
    } catch (err) {
      console.warn("CRM Stage Counter script failed safely:", err);
    }
  })();
  