from odoo import api, fields, models

class CRMStage(models.Model):
    _inherit = "crm.stage"

    lead_count = fields.Integer(compute="_compute_lead_count", store=False)

    def _compute_lead_count(self):
        cnt = {sid: 0 for sid in self.ids}
        if self.ids:
            rows = self.env['crm.lead'].read_group(
                [('stage_id', 'in', self.ids)], ['stage_id'], ['stage_id']
            )
            for r in rows:
                sid = r['stage_id'][0]
                cnt[sid] = r.get('stage_id_count', r.get('__count', 0)) or 0
        for s in self:
            s.lead_count = cnt.get(s.id, 0)

    def name_get(self):
        base = super().name_get()
        m = {s.id: s.lead_count for s in self}
        return [(sid, f"{name} ({m.get(sid, 0)})") for sid, name in base]
