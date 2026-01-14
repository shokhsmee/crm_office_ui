# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api, _
from odoo.tools import format_datetime

TG_PARAM_KEY = "warranty_bot.bot_token"       # Telegram bot token (ICP)
STAGE_NEW_PARAM = "warranty_bot.stage_new_id" # Optional ICP: explicit stage ID for "Yangi so'rovlar"

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

    # Flags to avoid duplicate sends
    notify_won_sent = fields.Boolean(default=False, copy=False)
    notify_new_sent = fields.Boolean(default=False, copy=False)

    # -----------------------------
    # Helpers: stage checks
    # -----------------------------
    def _is_won_now(self, r):
        """Won either by stage flag or probability >= 100."""
        return bool(getattr(r.stage_id, "is_won", False)) or (getattr(r, "probability", 0.0) >= 100.0)

    def _is_new_stage_now(self, r):
        """Is the lead currently in 'Yangi so‘rovlar' stage (by ICP id or name heuristics)."""
        st = r.stage_id
        if not st:
            return False
        # Prefer explicit ICP stage id if set
        try:
            sid = int(self.env["ir.config_parameter"].sudo().get_param(STAGE_NEW_PARAM, "0") or "0")
        except Exception:
            sid = 0
        if sid and st.id == sid:
            return True
        nm = (st.name or "").lower()
        # Heuristic fallbacks:
        # "Yangi so'rovlar", "Yangi", "New", "Yangi so‘rov", etc.
        return any(k in nm for k in ("yangi", "new", "so'rov", "so‘rov"))


    # def _is_confirmed_by_usta(self,r):
    #     st = r.stage_id
    #     if not st:
    #         return False

    #     try:
    #         ICP = int(self.env["ir.config_parameter"].sudo().get_param("kpi.stage.accept_id", "2") or "2")
    #     except Exception:
    #         ICP = 2
    #     if ICP and st.id = ICP:
    #         return True

    #     nm = (st.name or "").lower()
    #     return any(k in nm for k  in ("qabul","accept","qildi","QABUL QILINDI"))



    # -----------------------------
    # Telegram senders
    # -----------------------------
    def _send_usta_new_telegram(self):
        ICP = self.env["ir.config_parameter"].sudo()
        token = ICP.get_param(TG_PARAM_KEY)
        if not token:
            return
        for lead in self:
            usta = getattr(lead, "usta_id", False)
            chat_id = usta and getattr(usta, "tg_chat_id", False)
            if not chat_id:
                chat_id = getattr(lead, "tg_card_chat_id", False)
            if not chat_id:
                continue

            created = lead.create_date or fields.Datetime.now()
            when_tz = format_datetime(self.env, created, tz=self.env.user.tz or "UTC")
            responsible = (lead.user_id and lead.user_id.name) or "-"

            txt = (
                "🆕 <b>Yangi zayavka</b>\n\n"
                f"📄 <b>Murojaat:</b> {lead.name or '-'}\n"
                f"🔢 <b>Service #:</b> {getattr(lead, 'service_number', '') or '-'}\n"
                f"☎️ <b>Telefon:</b> {lead.phone or lead.partner_phone or (lead.partner_id and lead.partner_id.phone) or '-'}\n"
                f"📍 <b>Manzil:</b> {_fmt_addr(lead)}\n\n"
                f"🕒 <b>Yaratilgan:</b> {when_tz}\n"
                f"👤 <b>Mas’ul:</b> {responsible}\n"
                f"\n Zayavkani qabul qilish uchun Aktive zayavkalar bo'limini tanlang!"
            )

            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": str(chat_id), "text": txt, "parse_mode": "HTML"},
                    timeout=6,
                )
            except Exception:
                # never block business writes
                pass

    def _send_usta_won_telegram(self):
        ICP = self.env["ir.config_parameter"].sudo()
        token = ICP.get_param(TG_PARAM_KEY)
        if not token:
            return

        for lead in self:
            usta = getattr(lead, "usta_id", False)
            chat_id = usta and getattr(usta, "tg_chat_id", False)
            if not chat_id:
                chat_id = getattr(lead, "tg_card_chat_id", False)
            if not chat_id:
                continue

            when = fields.Datetime.now()
            when_tz = format_datetime(self.env, when, tz=self.env.user.tz or "UTC")
            operator_name = self.env.user.name or "-"
            responsible = (lead.user_id and lead.user_id.name) or "-"

            
            warning_txt = ""
            if getattr(lead, "qayta_zayavka", False):
                warning_txt = (
                    "\n\n"
                    "🔴 <b>Eslatma</b>\n"
                    "Mazkur zayavka bo‘yicha servis xizmati ko‘rsatilganiga qaramasdan, texnik muammo takrorlanganligi sababli "
                    "ushbu zayavka uchun haq hisoblanmaydi. Kelgusida bunday holatlar yuzaga kelmasligi uchun har bir zayavkaga "
                    "professional va mas’uliyat bilan yondashishingizni so‘raymiz. Rahmat."
                )
            
            txt = (
                "✅ <b>Tasdiqlandi</b>\n\n"
                f"📄 <b>Murojaat:</b> {lead.name or '-'}\n"
                f"🔢 <b>Seriya raqami:</b> {getattr(lead, 'service_number', '') or '-'}\n"
                f"☎️ <b>Telefon:</b> {lead.phone or lead.partner_phone or (lead.partner_id and lead.partner_id.phone) or '-'}\n"
                f"📍 <b>Manzil:</b> {_fmt_addr(lead)}\n\n"
                f"🕒 <b>Tasdiqlangan:</b> {when_tz}\n"
                f"👤 <b>Mas’ul xodim:</b> {responsible}\n"
                f"🖊️ <b>Tasdiqlagan:</b> {operator_name}"
                f"{warning_txt}"
            )

            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": str(chat_id), "text": txt, "parse_mode": "HTML"},
                    timeout=6,
                )
            except Exception:
                pass

    # -----------------------------
    # create/write hooks
    # -----------------------------
    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        # After create: send "new" only if in new stage and not sent yet
        to_notify = leads.filtered(lambda r: not r.notify_new_sent and self._is_new_stage_now(r))
        if to_notify:
            to_notify._send_usta_new_telegram()
            to_notify.with_context(__skip_new_notify__=True).sudo().write({"notify_new_sent": True})
        return leads

    def write(self, vals):
        # prevent recursion from our own flags
        ctx = self.env.context
        skip_new = ctx.get("__skip_new_notify__")
        skip_won = ctx.get("__skip_won_notify__")

        # Snapshots before write
        new_before = {r.id: self._is_new_stage_now(r) for r in self}
        won_before = {r.id: self._is_won_now(r) for r in self}

        res = super().write(vals)

        # Recompute after write
        records = self.sudo()
        # NEW stage transitions
        if not skip_new:
            newly_new = records.filtered(
                lambda r: not r.notify_new_sent and self._is_new_stage_now(r) and not new_before.get(r.id, False)
            )
            if newly_new:
                newly_new._send_usta_new_telegram()
                newly_new.with_context(__skip_new_notify__=True).sudo().write({"notify_new_sent": True})

        # WON transitions
        if not skip_won:
            newly_won = records.filtered(
                lambda r: not r.notify_won_sent and self._is_won_now(r) and not won_before.get(r.id, False)
            )
            if newly_won:
                newly_won._send_usta_won_telegram()
                newly_won.with_context(__skip_won_notify__=True).sudo().write({"notify_won_sent": True})

        return res
