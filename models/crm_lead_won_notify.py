# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api, _
from odoo.tools import format_datetime

TG_PARAM_KEY = "warranty_bot.bot_token"   # ir.config_parameter key holding your bot token

def _fmt_addr(lead):
    parts = [lead.street, lead.city, getattr(lead.state_id, "name", None), getattr(lead.country_id, "name", None)]
    parts = [p for p in parts if p]
    if parts:
        return ", ".join(parts)
    if lead.partner_id:
        return lead.partner_id.contact_address or lead.partner_id._display_address() or "-"
    return "-"

class CrmLead(models.Model):
    _inherit = "crm.lead"

    notify_won_sent = fields.Boolean(default=False, copy=False)

    def _send_usta_telegram(self):
        ICP = self.env["ir.config_parameter"].sudo()
        token = ICP.get_param(TG_PARAM_KEY)
        if not token:
            return

        for lead in self:
            # who to notify
            usta = getattr(lead, "usta_id", False)
            chat_id = usta and getattr(usta, "tg_chat_id", False)
            if not chat_id:
                # optional fallback to the saved card chat
                chat_id = getattr(lead, "tg_card_chat_id", False)
            if not chat_id:
                continue

            # timestamps in user's tz
            when = fields.Datetime.now()
            when_tz = format_datetime(self.env, when, tz=self.env.user.tz or "UTC")

            # operator who confirmed (the one who triggered this write)
            operator_name = self.env.user.name or "-"

            # responsible user
            responsible = (lead.user_id and lead.user_id.name) or "-"

            # build message
            txt = (
                "✅ <b>Tasdiqlandi</b>\n\n"
                f"📄 <b>Murojaat:</b> {lead.name or '-'}\n"
                f"🔢 <b>Seriya raqami:</b> {getattr(lead, 'service_number', '') or '-'}\n"
                f"☎️ <b>Telefon:</b> {lead.phone or lead.partner_phone or (lead.partner_id and lead.partner_id.phone) or '-'}\n"
                f"📍 <b>Manzil:</b> {_fmt_addr(lead)}\n\n"
                f"🕒 <b>Tasdiqlangan:</b> {when_tz}\n"
                f"👤 <b>Mas’ul xodim:</b> {responsible}\n"
                f"🖊️ <b>Tasdiqlagan:</b> {operator_name}"
            )

            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": str(chat_id), "text": txt, "parse_mode": "HTML"},
                    timeout=6,
                )
            except Exception:
                # swallow; don't block write
                pass

    def write(self, vals):
        # 1) Prevent recursion when we set the flag ourselves
        if self.env.context.get("__skip_won_notify__"):
            return super().write(vals)

        # 2) Snapshot: were these leads already "won" before this write?
        won_before = {
            rec.id: (bool(getattr(rec.stage_id, "is_won", False)) or (getattr(rec, "probability", 0.0) >= 100.0))
            for rec in self
        }

        res = super().write(vals)

        # 3) Compute: newly-won = now won AND was not won AND not yet notified
        newly_won = self.filtered(
            lambda r: not r.notify_won_sent
            and (bool(getattr(r.stage_id, "is_won", False)) or (getattr(r, "probability", 0.0) >= 100.0))
            and not won_before.get(r.id, False)
        )

        if newly_won:
            newly_won._send_usta_telegram()
            # 4) Set flag without re-entering write()
            newly_won.with_context(__skip_won_notify__=True).sudo().write({"notify_won_sent": True})

        return res
