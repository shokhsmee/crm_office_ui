/** Patch the CRM Kanban headers to display real lead counts **/
odoo.define('crm_office_ui.stage_counter', function (require) {
    "use strict";

    const KanbanColumn = require('web.KanbanColumn');

    KanbanColumn.include({
        _renderCounters() {
            this._super(...arguments);

            const $counter = this.$el.find('.o_kanban_counter');
            if (!$counter.length) return;

            const count = this.data && (this.data.count || this.data.__count || 0);
            // Replace or inject the number
            const $num = $('<div/>', {
                class: 'o_stage_real_count text-900 fw-bold ms-2',
                text: count,
                title: 'Lead count'
            });
            $counter.find('.o_animated_number').remove();  // remove zeros
            $counter.append($num);
        },
    });
});
