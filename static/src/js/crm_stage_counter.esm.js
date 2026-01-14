/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";
import { KanbanColumn } from "@web/views/kanban/kanban_column/kanban_column";

function pickCount(group) {
    return (
        group?.count ??
        group?.data?.count ??
        group?.data?.__count ??
        group?.aggregateValues?.__count ??
        group?.aggregateValues?.count ??
        0
    );
}

patch(KanbanColumn.prototype, "crm_office_ui_stage_counter", {
    setup() {
        // keep original
        if (super.setup) {
            super.setup(...arguments);
        }
        onMounted(() => this._injectRealCount());
    },

    willUpdateProps(nextProps) {
        if (super.willUpdateProps) {
            super.willUpdateProps(...arguments);
        }
        // update number after each re-render
        queueMicrotask(() => this._injectRealCount());
    },

    _injectRealCount() {
        const counterEl = this.el?.querySelector(".o_kanban_counter");
        if (!counterEl) return;

        // remove the two fake revenue/MRR counters
        counterEl.querySelectorAll(".o_animated_number").forEach((el) => el.remove());

        // ensure a single real-count node
        let badge = counterEl.querySelector(".o_stage_real_count");
        if (!badge) {
            badge = document.createElement("div");
            badge.className = "o_stage_real_count ms-2 text-900 text-nowrap";
            counterEl.appendChild(badge);
        }
        badge.textContent = String(pickCount(this.props?.group));
        badge.title = "Lead count";
    },
});
