# -*- coding: utf-8 -*-
from odoo import api, fields, models

STAGE_TITLES = [
    "Yangi so'rovlar",
    "Qabul qilindi",
    "Qabul qilinmadi",
    "Jarayonda",
    "Ish yakunlandi",
    "Tasdiqlandi",
    "Bekor qilindi",
]

class CcEmployee(models.Model):
    _inherit = "cc.employee"

    # Totals
    lead_active_count = fields.Integer(string="Faol", compute="_compute_lead_stats", store=False)
    lead_done_count   = fields.Integer(string="Tugallangan", compute="_compute_lead_stats", store=False)

    # Per-stage counters
    lead_stage_new_count               = fields.Integer(string="Yangi so'rovlar",   compute="_compute_lead_stats", store=False)
    lead_stage_qabul_count             = fields.Integer(string="Qabul qilindi",     compute="_compute_lead_stats", store=False)
    lead_stage_qabul_qilinmadi_count   = fields.Integer(string="Qabul qilinmadi",   compute="_compute_lead_stats", store=False)
    lead_stage_jarayonda_count         = fields.Integer(string="Jarayonda",         compute="_compute_lead_stats", store=False)
    lead_stage_yakun_count             = fields.Integer(string="Ish yakunlandi",    compute="_compute_lead_stats", store=False)
    lead_stage_tasdiqlandi_count       = fields.Integer(string="Tasdiqlandi",       compute="_compute_lead_stats", store=False)
    lead_stage_bekor_count             = fields.Integer(string="Bekor qilindi",     compute="_compute_lead_stats", store=False)

    def _compute_lead_stats(self):
        Lead = self.env["crm.lead"].sudo()

        # Build map: title -> [stage_ids]
        stage_map = {}
        if STAGE_TITLES:
            stages = self.env["crm.stage"].sudo().search([("name", "in", STAGE_TITLES)])
            for st in stages:
                stage_map.setdefault(st.name, []).append(st.id)

        for emp in self:
            # defaults
            emp.lead_active_count = 0
            emp.lead_done_count = 0
            emp.lead_stage_new_count = 0
            emp.lead_stage_qabul_count = 0
            emp.lead_stage_qabul_qilinmadi_count = 0
            emp.lead_stage_jarayonda_count = 0
            emp.lead_stage_yakun_count = 0
            emp.lead_stage_tasdiqlandi_count = 0
            emp.lead_stage_bekor_count = 0

            if not emp.id:
                continue

            base = [("usta_id", "=", emp.id), ("active", "=", True)]

            # totals
            emp.lead_active_count = Lead.search_count(base + [("stage_id.is_won", "=", False)])
            emp.lead_done_count   = Lead.search_count(base + [("stage_id.is_won", "=", True)])

            # helper
            def count_for(title):
                ids = stage_map.get(title, [])
                return Lead.search_count(base + [("stage_id", "in", ids)]) if ids else 0

            # per-stage
            emp.lead_stage_new_count             = count_for("Yangi so'rovlar")
            emp.lead_stage_qabul_count           = count_for("Qabul qilindi")
            emp.lead_stage_qabul_qilinmadi_count = count_for("Qabul qilinmadi")
            emp.lead_stage_jarayonda_count       = count_for("Jarayonda")
            emp.lead_stage_yakun_count           = count_for("Ish yakunlandi")
            emp.lead_stage_tasdiqlandi_count     = count_for("Tasdiqlandi")
            emp.lead_stage_bekor_count           = count_for("Bekor qilindi")

    # === Open helpers (unchanged) ===
    def _action_open_leads(self, extra_domain=None, name="Murojaatlar"):
        self.ensure_one()
        action = self.env.ref("crm.crm_lead_action_pipeline").read()[0]
        dom = [('usta_id', '=', self.id)]
        if extra_domain:
            dom += extra_domain
        action['domain'] = dom
        action['name'] = name
        action['view_mode'] = 'kanban,tree,form'
        return action

    def action_open_active_leads(self):
        return self._action_open_leads(
            extra_domain=[('stage_id.is_won', '=', False), ('active', '=', True)],
            name="Faol murojaatlar"
        )

    def action_open_done_leads(self):
        return self._action_open_leads(
            extra_domain=[('stage_id.is_won', '=', True), ('active', '=', True)],
            name="Tugallangan murojaatlar"
        )

    def action_open_stage_new(self):              return self._open_by_stage("Yangi so'rovlar")
    def action_open_stage_qabul(self):            return self._open_by_stage("Qabul qilindi")
    def action_open_stage_qabul_qilinmadi(self):  return self._open_by_stage("Qabul qilinmadi")
    def action_open_stage_jarayonda(self):        return self._open_by_stage("Jarayonda")
    def action_open_stage_yakun(self):            return self._open_by_stage("Ish yakunlandi")
    def action_open_stage_tasdiq(self):           return self._open_by_stage("Tasdiqlandi")
    def action_open_stage_bekor(self):            return self._open_by_stage("Bekor qilindi")

    def _open_by_stage(self, title):
        self.ensure_one()
        stage_ids = self.env['crm.stage'].sudo().search([('name', '=', title)]).ids
        return self._action_open_leads(
            extra_domain=[('stage_id', 'in', stage_ids), ('active', '=', True)],
            name=title
        )
