odoo.define('crm_office_ui.crm_stage_colors', function (require) {
    "use strict";
    const ajax = require('web.ajax');
  
    function throttle(fn, wait) {
      let t, last = 0;
      return function () {
        const now = Date.now();
        if (now - last > wait) { last = now; fn(); }
        else { clearTimeout(t); t = setTimeout(() => { last = Date.now(); fn(); }, wait); }
      };
    }
  
    let STAGE_COLORS = null;
  
    async function loadStageColors() {
      const resp = await ajax.jsonRpc('/web/dataset/call_kw', 'call', {
        model: 'crm.stage',
        method: 'search_read',
        args: [[], ['id', 'color_hex', 'text_color_hex']],
        kwargs: { limit: 2000 },
      });
      const map = {};
      resp.forEach(s => { if (s.color_hex) map[s.id] = { bg: s.color_hex, fg: s.text_color_hex || '#fff' }; });
      STAGE_COLORS = map;
    }
  
    function applyKanban() {
      if (!STAGE_COLORS) return;
      document.querySelectorAll('.o_kanban_group').forEach(g => {
        const id = parseInt(g.getAttribute('data-id') || '0', 10);
        const c = STAGE_COLORS[id];
        if (!c) return;
        const header = g.querySelector('.o_kanban_header');
        if (header) {
          header.style.backgroundColor = c.bg;
          header.style.color = c.fg;
        }
      });
    }
  
    function applyList() {
      if (!STAGE_COLORS) return;
      document.querySelectorAll('.o_list_view table tbody tr').forEach(tr => {
        const td = tr.querySelector('td.o_data_cell[data-name="stage_id"], td[data-field="stage_id"]');
        if (!td) return;
        const badge = td.querySelector('.o_m2o_badge, .o_field_widget, span, a') || td;
        // stage id’ni topishga urinamiz
        let sid = parseInt(badge.getAttribute('data-res-id') || td.getAttribute('data-res-id') || '0', 10);
        if (!sid) {
          const m = (badge.getAttribute('title') || '').match(/\((\d+)\)$/);
          if (m) sid = parseInt(m[1], 10);
        }
        const c = STAGE_COLORS[sid];
        if (!c) return;
        badge.style.backgroundColor = c.bg;
        badge.style.color = c.fg;
        badge.style.padding = '2px 6px';
        badge.style.borderRadius = '6px';
        badge.style.fontWeight = '600';
        badge.style.display = 'inline-block';
      });
    }
  
    const recolor = throttle(() => { applyKanban(); applyList(); }, 250);
  
    async function boot() {
      try {
        await loadStageColors();
        recolor();
        const obs = new MutationObserver(recolor);
        obs.observe(document.body, { childList: true, subtree: true });
        window.addEventListener('resize', recolor);
      } catch (e) { /* silent */ }
    }
  
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  });
  