odoo.define('crm_office_ui.web_widget_html_raw', function (require) {
    "use strict";
    const fieldRegistry = require('web.field_registry');
    const AbstractField = require('web.AbstractField');

    const HtmlRaw = AbstractField.extend({
        supportedFieldTypes: ['html'],
        _render: function () {
            this.$el.html(this.value || '');
        },
    });

    fieldRegistry.add('web_widget_html_raw', HtmlRaw);
});
