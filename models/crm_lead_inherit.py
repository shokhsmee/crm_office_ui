# crm_office_ui/models/crm_lead_timing.py
# -*- coding: utf-8 -*-
from odoo import api, fields, models

_ACCEPT_KEYS  = ("qabul", "accept")
_DONE_KEYS    = ("ish yakunlandi", "yakun", "tasdiq", "finished", "done", "won")

class CrmLead(models.Model):
    _inherit = "crm.lead"

    # stamps + badge for current stage
    stage_entered_dt = fields.Datetime(copy=False, readonly=True)
    stage_elapsed_badge = fields.Char(compute="_compute_stage_elapsed_badge", store=False)

    # business stamps
    accepted_dt  = fields.Datetime(copy=False, readonly=True)
    completed_dt = fields.Datetime(copy=False, readonly=True)

    # total work time (accept → done)
    _work_duration_secs = fields.Float(compute="_compute_work_duration_core", store=False)
    work_duration_hours = fields.Float(string="Ishga ketgan vaqt (soat)",
                                       compute="_compute_work_duration_hours", store=False)
    work_duration_badge = fields.Char(string="Jami ish vaqti",
                                      compute="_compute_work_duration_badge", store=False)

    # ---------- helpers ----------
    @staticmethod
    def _fmt_badge_from_seconds(seconds: float) -> str:
        seconds = max(0, int(seconds))
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        return f"{days}d"

    @api.depends("stage_entered_dt", "stage_id")
    def _compute_stage_elapsed_badge(self):
        now = fields.Datetime.now()
        to_dt = fields.Datetime.to_datetime
        for rec in self:
            base = rec.stage_entered_dt or rec.write_date or rec.create_date
            secs = (to_dt(now) - to_dt(base)).total_seconds() if base else 0.0
            rec.stage_elapsed_badge = self._fmt_badge_from_seconds(secs)

    def _stage_timeline_from_history(self):
        """[(dt, stage_name_lower), ...] oldest→newest incl. 'now/current' closure."""
        self.ensure_one()
        Message = self.env["mail.message"].sudo()
        msgs = Message.search([("model", "=", "crm.lead"), ("res_id", "=", self.id)],
                              order="date asc, id asc")
        timeline = []
        for msg in msgs:
            for tv in (msg.tracking_value_ids or []):
                fname = (getattr(tv, "field", None)
                         or getattr(tv, "field_name", None)
                         or getattr(tv, "field_desc", None) or "")
                if str(fname).strip().lower() not in ("stage_id", "stage"):
                    continue
                name = (getattr(tv, "new_value_char", "") or "").strip()
                if not name and getattr(tv, "new_value", None):
                    name = str(tv.new_value).split(",")[0].strip()
                if not name:
                    continue
                dt = msg.date or msg.create_date
                if dt:
                    timeline.append((dt, name.lower()))
        if self.stage_id and self.stage_id.name:
            timeline.append((fields.Datetime.now(), (self.stage_id.name or "").lower()))
        return timeline

    @api.depends("accepted_dt", "completed_dt", "stage_id")
    def _compute_work_duration_core(self):
        """Compute total seconds from first Accept to first Done."""
        to_dt = fields.Datetime.to_datetime
        for rec in self:
            # Fast path if we have stamps
            if rec.accepted_dt and rec.completed_dt:
                rec._work_duration_secs = max(
                    0.0,
                    (to_dt(rec.completed_dt) - to_dt(rec.accepted_dt)).total_seconds(),
                )
                continue
            # Fallback: rebuild from chatter
            secs = 0.0
            tl = rec._stage_timeline_from_history()
            if tl:
                started = None
                last_dt = None
                for dt, name in tl:
                    if started is None:
                        if any(k in name for k in _ACCEPT_KEYS):
                            started = dt
                            last_dt = dt
                        continue
                    secs += (to_dt(dt) - to_dt(last_dt)).total_seconds()
                    last_dt = dt
                    if any(k in name for k in _DONE_KEYS):
                        break
            rec._work_duration_secs = max(0.0, secs)

    @api.depends("_work_duration_secs")
    def _compute_work_duration_hours(self):
        for rec in self:
            rec.work_duration_hours = round(rec._work_duration_secs / 3600.0, 2)

    @api.depends("_work_duration_secs")
    def _compute_work_duration_badge(self):
        for rec in self:
            rec.work_duration_badge = self._fmt_badge_from_seconds(rec._work_duration_secs)

    # Stamp times on stage change to keep future computes fast
    def write(self, vals):
        stage_changed = "stage_id" in vals
        res = super().write(vals)
        if stage_changed:
            now = fields.Datetime.now()
            for rec in self.sudo():
                rec.stage_entered_dt = now
                nm = (rec.stage_id.name or "").lower()
                if any(k in nm for k in _ACCEPT_KEYS) and not rec.accepted_dt:
                    rec.accepted_dt = now
                if getattr(rec.stage_id, "is_won", False) or any(k in nm for k in _DONE_KEYS):
                    rec.completed_dt = now
        return res
