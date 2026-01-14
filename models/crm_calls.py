from odoo import api, fields, models, _

def _digits_only(num):
    return "".join(ch for ch in str(num or "") if ch.isdigit())


class CrmLeadUtel(models.Model):
    _inherit = "crm.lead"

    utel_call_count = fields.Integer(
        string="Qo'ng'iroqlar",
        compute="_compute_utel_call_count",
        store=False,
    )

    # ---- NEW: phone-based domain only ----
    def _utel_domain(self):
        """Domain for utel.call: only by phone digits (lead + partner), no partner_id."""
        self.ensure_one()
        Call = self.env['utel.call'].sudo()

        src_f = 'src_norm' if 'src_norm' in Call._fields else 'src'
        dst_f = 'dst_norm' if 'dst_norm' in Call._fields else 'dst'

        phones = []

        # lead phones
        if getattr(self, 'phone', None):
            phones.append(self.phone)
        if getattr(self, 'mobile', None):
            phones.append(self.mobile)

        # partner phones, still as numbers (not partner_id)
        if self.partner_id:
            if self.partner_id.phone:
                phones.append(self.partner_id.phone)
            if self.partner_id.mobile:
                phones.append(self.partner_id.mobile)

        # collect unique 7-digit tails
        tails = set()
        for p in phones:
            d = _digits_only(p)
            if not d:
                continue
            tail = d[-7:] if len(d) > 7 else d
            if tail:
                tails.add(tail)

        if not tails:
            return []

        # build OR domain: (src ilike t1) OR (dst ilike t1) OR (src ilike t2) OR ...
        conds = []
        for t in tails:
            conds.append((src_f, 'ilike', t))
            conds.append((dst_f, 'ilike', t))

        dom = []
        for cond in conds:
            if not dom:
                dom = [cond]
            else:
                dom = ['|'] + dom + [cond]
        return dom

    @api.depends('partner_id', 'phone', 'mobile')
    def _compute_utel_call_count(self):
        Call = self.env['utel.call'].sudo()
        for lead in self:
            try:
                dom = lead._utel_domain()
                lead.utel_call_count = Call.search_count(dom) if dom else 0
            except Exception:
                lead.utel_call_count = 0

    def action_open_utel_calls(self):
        self.ensure_one()
        dom = self._utel_domain() or [('id', '=', 0)]

        Act = self.env['ir.actions.act_window'].sudo()
        found = Act.search([('res_model', '=', 'utel.call')], limit=1)
        if found:
            action = found.read()[0]
            action['domain'] = dom
            action['context'] = {'default_partner_id': self.partner_id.id} if self.partner_id else {}
            return action

        return {
            'name': _("Qo'ng'iroqlar"),
            'type': 'ir.actions.act_window',
            'res_model': 'utel.call',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': dom,
            'context': {'default_partner_id': self.partner_id.id} if self.partner_id else {},
        }
