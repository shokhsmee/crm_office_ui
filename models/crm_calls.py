# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.osv import expression  # for safe domain OR building

def _digits_only(num):
    return "".join(ch for ch in str(num or "") if ch.isdigit())

class CrmLeadUtel(models.Model):
    _inherit = "crm.lead"

    utel_call_count = fields.Integer(
        string="Qo'ng'iroqlar",
        compute="_compute_utel_call_count",
        store=False,
    )

    # ---------- helpers ----------
    def _utel_tail_pairs(self):
        """Return OR-able domain pairs for src/dst (or src_norm/dst_norm) by last 7 digits."""
        Call = self.env['utel.call'].sudo()
        # Prefer normalized fields if available; fallback to raw names
        src_f = 'src_norm' if 'src_norm' in Call._fields else 'src'
        dst_f = 'dst_norm' if 'dst_norm' in Call._fields else 'dst'

        phones = []
        if getattr(self, 'phone', None):
            phones.append(self.phone)
        if getattr(self, 'mobile', None):
            phones.append(self.mobile)

        digits = [_digits_only(p) for p in phones if p]
        if not digits:
            return []

        pairs = []
        for d in digits:
            tail = d[-7:] if len(d) > 7 else d
            # (src LIKE tail) OR (dst LIKE tail)
            pairs.append(['|', (src_f, 'ilike', tail), (dst_f, 'ilike', tail)])
        return pairs

    def _utel_domain(self):
        """Build a valid domain for utel.call based on partner or phone tails."""
        self.ensure_one()
        if self.partner_id:
            return [('partner_id', '=', self.partner_id.id)]
        pairs = self._utel_tail_pairs()
        if not pairs:
            return []

        # Nest pairs with ORs: ['|', pair1, ['|', pair2, pair3]] ...
        dom = pairs[0]
        for p in pairs[1:]:
            dom = ['|', dom, p]
        return dom

    # ---------- compute ----------
    @api.depends('partner_id', 'phone', 'mobile')
    def _compute_utel_call_count(self):
        Call = self.env['utel.call'].sudo()
        for lead in self:
            try:
                dom = lead._utel_domain()
                lead.utel_call_count = Call.search_count(dom) if dom else 0
            except Exception:
                lead.utel_call_count = 0

    # ---------- action ----------
    def action_open_utel_calls(self):
        """Open utel.call filtered to this lead’s contact or phone tails."""
        self.ensure_one()
        dom = self._utel_domain() or [('id', '=', 0)]

        Act = self.env['ir.actions.act_window'].sudo()
        found = Act.search([('res_model', '=', 'utel.call')], limit=1)
        if found:
            action = found.read()[0]
            action['domain'] = dom
            action['context'] = {'default_partner_id': self.partner_id.id} if self.partner_id else {}
            return action

        # Fallback: basic action
        return {
            'name': _("Qo'ng'iroqlar"),
            'type': 'ir.actions.act_window',
            'res_model': 'utel.call',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': dom,
            'context': {'default_partner_id': self.partner_id.id} if self.partner_id else {},
        }
