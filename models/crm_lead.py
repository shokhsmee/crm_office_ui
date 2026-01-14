# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from urllib.parse import quote_plus
import requests
from eskiz_sms import EskizSMS
from eskiz_sms.exceptions import BadRequest, InvalidCredentials

SERVICE_SEQ_CODE = "crm.lead.service.number"

OL0V_TAG_NAME = "Olov🔥"
OL0V_BONUS_AMOUNT = 50000.0  # so'm


PARAM_KM_RATE = "crm.distance_km_rate"

class CrmLead(models.Model):
    _inherit = "crm.lead"

    category_type = fields.Selection(
        [("hamkorli", "Hamkorli"), ("shikoyat", "Shikoyat"), ("servis", "Servis")],
        string="Murojaat turi", tracking=True,
    )

    usta_id = fields.Many2one("cc.employee", string="Usta", tracking=True)

    region_id = fields.Many2one(
        "cc.region", string="Tuman (Region)",
        domain="[('state_id','=',state_id)]", tracking=True
    )

    country_id = fields.Many2one(
        "res.country", string="Davlat",
        default=lambda self: self.env.ref("base.uz", raise_if_not_found=False)
            or self.env["res.country"].search([("code", "=", "UZ")], limit=1),
    )

    work_amount = fields.Monetary(string="Ish summasi")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id
    )

    work_text = fields.Text(
        string="Ish tasnifi",
        tracking=True,
        help="Ishning qisqa tasnifi: masalan, diagnostika, kompressor almashtirish, drenaj tozalash va h.k."
    )

    accept_at = fields.Datetime(copy=False)
    start_at = fields.Datetime(copy=False)
    finish_at = fields.Datetime(copy=False)

    work_time_spent = fields.Float(string="Ishga ketgan vaqt (soat)")
    work_time_pretty = fields.Char(
        string="Ishga ketgan vaqt",
        compute="_compute_work_time_pretty",
        store=False,
    )

    customer_rating = fields.Integer(
        string="Mijoz reytingi (0-10)",
        help="Mijozdan olingan baho. 9-10:3 ball, 8-9:2, 7-8:1.5, 6-7:0.5",
    )

    tasks_done_count = fields.Integer(
        string="Bajarilgan topshiriqlar soni",
        help="Kunlik topshiriqlar/yo'riqnomalar bo'yicha. 0..∞. Max 3 ball (normalize).",
    )

    kpi_result_id = fields.Many2one(
        "cc.kpi.result",
        string="KPI natija",
        copy=False,
        readonly=True,
        ondelete="set null",
    )

    auto_fill_from_purchases = fields.Boolean(
        string="Avto to'ldirish (xaridlardan)",
        default=True,
        help="Kontakt tanlanganda 'Sotilgan mahsulot' bo'limi mijozning so'nggi xaridlaridan avtomatik to'ldiriladi."
    )
    
    photo_gallery_html = fields.Html(
        string="Foto galereya",
        compute="_compute_photo_gallery_html",
        sanitize=False
    )
    
    
    new_to_accept_hours = fields.Float(string="New→Qabul (soat)", copy=False)
    accept_to_start_hours = fields.Float(string="Qabul→Jarayon (soat)", copy=False)
    start_to_finish_hours = fields.Float(string="Jarayon→Yakun (soat)", copy=False)
    finish_to_confirm_hours = fields.Float(string="Yakun→Tasdiq (soat)", copy=False)

    total_to_finish_hours = fields.Float(string="New→Yakun (soat)", copy=False)
    total_to_confirm_hours = fields.Float(string="New→Tasdiq (soat)", copy=False)


    qayta_zayavka = fields.Boolean(
        string="Qayta zayavka",
        tracking=True,
        help="ON bo'lsa: bu mijozning qayta murojaati. Tasdiqlanganda usta uchun KPI va bonus/finance berilmaydi."
    )


    @api.depends('photo_attachment_ids', 'photo_attachment_ids.mimetype', 'photo_attachment_ids.write_date')
    def _compute_photo_gallery_html(self):
        for rec in self:
            imgs = rec.photo_attachment_ids.filtered(lambda a: (a.mimetype or '').startswith('image/'))
            if not imgs:
                rec.photo_gallery_html = ''
                continue

            html = ["""
    <style>
    .cl-gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px}
    .cl-gallery-grid img{width:100%;height:110px;object-fit:cover;border-radius:8px;cursor:pointer;display:block}
    .cl-viewer{position:fixed;top:0;left:0;width:60vw;height:100vh;background:#000c;display:none;z-index:9999;
                justify-content:flex-start;align-items:center;padding-left:20px}
    .cl-viewer img{max-height:90vh;max-width:55vw;border-radius:8px;box-shadow:0 0 20px #000}
    .cl-viewer.active{display:flex;animation:fadeIn .2s ease}
    @keyframes fadeIn{from{opacity:0}to{opacity:1}}
    .cl-viewer .cl-close{position:absolute;top:20px;left:20px;font-size:26px;color:white;text-decoration:none;cursor:pointer}
    </style>
    <div class="cl-gallery-grid">
    """]

            for a in imgs:
                url = f"/web/image/ir.attachment/{a.id}/datas"
                html.append(f'<img src="{url}" data-full="{url}" alt="">')
            html.append("""
    </div>
    <div id="cl-viewer" class="cl-viewer">
    <span class="cl-close">×</span>
    <img src="">
    </div>
    <script>
    (function(){
        const viewer=document.getElementById('cl-viewer');
        const vimg=viewer.querySelector('img');
        document.querySelectorAll('.cl-gallery-grid img').forEach(el=>{
        el.addEventListener('click',()=>{
            vimg.src=el.dataset.full;
            viewer.classList.add('active');
        });
        });
        viewer.querySelector('.cl-close').onclick=()=>viewer.classList.remove('active');
        viewer.onclick=e=>{if(e.target===viewer) viewer.classList.remove('active');};
    })();
    </script>
    """)

            rec.photo_gallery_html = ''.join(html)


    @api.onchange('photo_attachment_ids')
    def _onchange_photo_gallery_live(self):
        for rec in self:
            rec._compute_photo_gallery_html()
            
            
    @api.onchange('partner_id')
    def _onchange_partner_fill_products_from_purchases(self):
        for lead in self:
            if not lead.partner_id or not lead.auto_fill_from_purchases:
                continue
            if lead.product_line_ids:
                continue
            lead._load_products_from_partner_purchases(limit_per_partner=25)

    def action_load_products_from_purchases(self):
        for lead in self:
            if not lead.partner_id:
                raise UserError(_("Avval Kontaktni tanlang."))
            lead._load_products_from_partner_purchases(limit_per_partner=50)
        return True

    
    
    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        from math import radians, sin, cos, asin, sqrt
        R = 6371.0088
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        return R * 2 * asin(sqrt(a))

    def _parse_latlng_from_url(self, url: str):
        """Google Maps/Maps links: tries q=lat,lng | ll= | /@lat,lng, | ?query=lat,lng"""
        from urllib.parse import urlparse, parse_qs, unquote
        if not url:
            return (None, None)
        u = urlparse(url)
        qs = {k: v[0] for k, v in parse_qs(u.query).items() if v}
        # q=lat,lng  |  ll=lat,lng  |  query=lat,lng
        for key in ("q", "ll", "query"):
            val = qs.get(key)
            if val and "," in val:
                a, b = val.split(",", 1)
                try:
                    return (float(a.strip()), float(b.strip()))
                except Exception:
                    pass
        # path .../@lat,lng,zoom...
        path = unquote(u.path or "")
        if "/@" in path:
            chunk = path.split("/@")[-1].split("/", 1)[0]
            parts = chunk.split(",")
            if len(parts) >= 2:
                try:
                    return (float(parts[0]), float(parts[1]))
                except Exception:
                    pass
        return (None, None)

    # --- Fields ---
    distance_km = fields.Float(string="Masofa (km)", digits=(12, 3))
    distance_amount = fields.Monetary(string="Yo‘l puli", currency_field="currency_id")

    def action_calc_distance_km(self):
        ICP = self.env["ir.config_parameter"].sudo()
        rate = float(ICP.get_param(PARAM_KM_RATE, "0") or 0)  # so'm/km
        for rec in self:
            if not rec.usta_id:
                raise UserError(_("Usta tanlanmagan."))
            if not (rec.usta_id.geo_lat and rec.usta_id.geo_lng):
                raise UserError(_("Ustaning koordinatasi (lat/lng) yo‘q."))
            lat2, lng2 = self._parse_latlng_from_url(rec.location_url or "")
            if lat2 is None or lng2 is None:
                raise UserError(_("Manzil URL ichidan koordinata topilmadi (Google Maps havolasini bering)."))
            km = self._haversine_km(rec.usta_id.geo_lat, rec.usta_id.geo_lng, lat2, lng2)
            rec.distance_km = round(km, 3)
            rec.distance_amount = round(km * rate, 0)
            rec.message_post(body=_("Masofa hisoblandi: %(km).3f km × %(rate).0f so'm/km = %(sum).0f so'm") % {
                "km": rec.distance_km, "rate": rate, "sum": rec.distance_amount
            })
        return True
    
    
    def _load_products_from_partner_purchases(self, limit_per_partner=25):
        SaleSync = self.env['product.sale.sync'].sudo()
        for lead in self:
            if not lead.partner_id:
                continue
            lines = SaleSync.search(
                [('partner_id', '=', lead.partner_id.id)],
                order='sale_date desc, id desc',
                limit=limit_per_partner
            )
            if not lines:
                continue
            seen = set()
            commands = []
            for ss in lines:
                pid = ss.product_id.id if ss.product_id else False
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                commands.append((0, 0, {
                    'product_id': pid,
                    'description': ss.name or ss.product_id.display_name,
                    'quantity': 1.0,
                    'price_unit': ss.price_unit or ss.product_id.list_price or 0.0,
                    'sync_line_id': ss.id,
                }))
            if commands:
                if not lead.product_line_ids:
                    lead.product_line_ids = commands
                else:
                    lead.product_line_ids = [(5, 0, 0)] + commands

    location_url = fields.Char(string="Manzil URL", help="Google Maps yoki boshqa manzil havolasi")

    # ---- helpers ----
    def _has_olov_tag(self):
        self.ensure_one()
        try:
            return any(t.name == OL0V_TAG_NAME for t in (self.tag_ids or self.env['crm.tag']))
        except Exception:
            return False

    def _elapsed_hours_accept_to_finish(self):
        self.ensure_one()
        end = self.finish_at
        start = self.new_at or self.accept_at or self.start_at or self.create_date
        if not (start and end):
            return 0.0
        return round((end - start).total_seconds() / 3600.0, 2)

    def _get_or_create_fin_kind(self):
        Kind = self.env["cc.finance.kind"].sudo()
        kind = Kind.search([("code", "=", "kpi_bonus")], limit=1)
        if not kind:
            kind = Kind.create({"name": "KPI Bonus", "code": "kpi_bonus", "direction": "income"})
        return kind

    def _apply_olov_bonus_if_applicable(self):
        Finance = self.env["cc.finance"].sudo()
        kind = self._get_or_create_fin_kind()
        for lead in self:
            if not (lead.finish_at and lead.usta_id and lead._has_olov_tag()):
                continue
            hours = lead._elapsed_hours_accept_to_finish()
            if hours <= 24.0:
                existing = Finance.search([
                    ("lead_id", "=", lead.id),
                    ("employee_id", "=", lead.usta_id.id),
                    ("direction", "=", "income"),
                    ("amount", "=", OL0V_BONUS_AMOUNT),
                    ("note", "=", "Olov🔥 statuslik zayavkani 2 kun ichida yakunlaganligi uchun kpi bonus"),
                ], limit=1)
                if not existing:
                    Finance.create({
                        "date": fields.Date.context_today(self),
                        "employee_id": lead.usta_id.id,
                        "direction": "income",
                        "amount": OL0V_BONUS_AMOUNT,
                        "kind_id": kind.id,
                        "lead_id": lead.id,
                        "note": "Olov🔥 statuslik zayavkani 2 kun ichida yakunlaganligi uchun kpi bonus",
                    })
                    lead.message_post(
                        body=_("Ustaga KPI bonus berildi: %(amt)s so'm ---> Olov🔥 statuslik zayavkani 2 kun ichida bajargani uchun.") % {
                            "amt": int(OL0V_BONUS_AMOUNT)
                        },
                        subtype_xmlid="mail.mt_note"
                    )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        domain = []
        if name:
            domain = [('service_number', operator, name)] + args
            leads = self.search(domain, limit=limit)
            if leads:
                return leads.name_get()

        return super(CrmLead, self).name_search(
            name=name,
            args=args,
            operator=operator,
            limit=limit,
        )




    @api.depends("accept_at", "start_at", "finish_at", "write_date")
    def _compute_work_time_pretty(self):
        now = fields.Datetime.now()
        for lead in self:
            start = lead.new_at or lead.accept_at or lead.start_at or lead.create_date
            end = lead.finish_at or now
            if not start:
                lead.work_time_pretty = "-"
                continue
            td = end - start
            total = int(td.total_seconds())
            days, rem = divmod(total, 86400)
            hours, rem = divmod(rem, 3600)
            minutes = rem // 60
            parts = []
            if days:
                parts.append(f"{days} kun")
            if hours:
                parts.append(f"{hours} soat")
            parts.append(f"{minutes} min")
            lead.work_time_pretty = " ".join(parts)

    @staticmethod
    def _humanize_seconds(seconds: float) -> str:
        total_minutes = int(round(seconds / 60.0))
        days, rem_min = divmod(total_minutes, 60 * 24)
        hours, minutes = divmod(rem_min, 60)
        parts = []
        if days:
            parts.append(f"{days} kun")
        if hours:
            parts.append(f"{hours} soat")
        parts.append(f"{minutes} min")
        return " ".join(parts)

    photo_attachment_ids = fields.Many2many(
        "ir.attachment", "crm_lead_photo_rel", "lead_id", "attachment_id",
        string="Foto hisobot",
        help="Rasmlarni biriktiring (yoki chatterga yuklang).",
    )

    product_line_ids = fields.One2many("crm.lead.product.line", "lead_id", string="Mahsulotlar")

    product_total_amount = fields.Monetary(
        string="Mahsulotlar jami",
        compute="_compute_product_total",
        store=True,
        currency_field="currency_id"
    )

    @api.depends("product_line_ids.subtotal")
    def _compute_product_total(self):
        for lead in self:
            lead.product_total_amount = sum(lead.product_line_ids.mapped('subtotal'))

    show_won_button = fields.Boolean(
        string="Show Won Button",
        compute="_compute_show_won_button",
        store=False
    )
    warranty_sms_sent = fields.Boolean(
        string="Warranty SMS sent",
        default=False,
        copy=False,
    )

    @api.depends('stage_id', 'stage_id.name')
    def _compute_show_won_button(self):
        for lead in self:
            lead.show_won_button = bool(lead.stage_id and lead.stage_id.name == 'Ish yakunlandi')

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        return super(CrmLead, self).get_view(view_id=view_id, view_type=view_type, **options)

    tg_card_chat_id = fields.Char("TG Card Chat")
    tg_card_msg_id = fields.Char("TG Card Msg")

    @api.onchange("state_id", "region_id")
    def _onchange_location_filter_usta(self):
        dom = [("is_usta", "=", True), ("active", "=", True)]
        if self.region_id:
            dom.append(("service_region_ids", "in", [self.region_id.id]))
        elif self.state_id:
            dom.append(("state_ids", "in", [self.state_id.id]))
        if self.usta_id:
            if self.region_id and self.region_id not in self.usta_id.service_region_ids:
                self.usta_id = False
            elif self.state_id and not self.region_id and self.state_id not in self.usta_id.state_ids:
                self.usta_id = False
        return {"domain": {"usta_id": dom}}

    @api.onchange('usta_id')
    def _check_usta_region_selected(self):
        if self.usta_id and not self.region_id:
            self.usta_id = False
            return {
                'warning': {
                    'title': "Diqqat!",
                    'message': "Oldin murojaat hududini belgilang! Avval Viloyat va Tumanni tanlang, keyin Ustani tanlashingiz mumkin."
                }
            }

    @api.constrains('usta_id', 'region_id')
    def _validate_usta_region(self):
        for lead in self:
            if lead.usta_id and lead.region_id:
                if lead.region_id not in lead.usta_id.service_region_ids:
                    raise UserError(
                        f"Tanlangan usta ({lead.usta_id.name}) bu hudud ({lead.region_id.name}) uchun xizmat ko'rsatmaydi. "
                        f"Iltimos, boshqa ustani tanlang yoki ustaning ish hududini yangilang."
                    )

    cc_move_ids = fields.One2many("cc.zapchast.move", "crm_service_id",
                                  string="Zapchastlar tarixi (lead)")

    cc_move_out_count = fields.Integer(
        string="Ishlatilgan zapchastlar soni",
        compute="_compute_cc_move_out_count",
    )

    @api.depends("cc_move_ids.move_type")
    def _compute_cc_move_out_count(self):
        for lead in self:
            lead.cc_move_out_count = sum(1 for m in lead.cc_move_ids if m.move_type == "out")

    def action_open_used_zapchasts(self):
        self.ensure_one()
        action = self.env.ref("crm_office_ui.action_cc_zapchast_move_lead").read()[0]
        action["domain"] = [("crm_service_id", "=", self.id), ("move_type", "=", "out")]
        action["context"] = {"default_crm_service_id": self.id}
        return action

    # ==== Finance integration (cc_finance) ====
    finance_ids = fields.One2many("cc.finance", "lead_id", string="Finance Records")
    finance_count = fields.Integer(compute="_compute_finance_stats")
    finance_amount_sum = fields.Monetary(currency_field="currency_id",
                                         compute="_compute_finance_stats")

    @api.depends(
        "finance_ids",
        "finance_ids.amount",
        "finance_ids.signed_amount",
        "finance_ids.direction",
        "finance_ids.lead_id",
    )
    def _compute_finance_stats(self):
        for lead in self:
            lead.finance_count = 0
            lead.finance_amount_sum = 0.0
        lead_ids = [l.id for l in self if l.id]
        if not lead_ids:
            return
        Finance = self.env["cc.finance"].sudo()
        rows = Finance.read_group(
            domain=[("lead_id", "in", lead_ids), ("state", "=", "confirmed")],
            fields=["lead_id", "id:count"],
            groupby=["lead_id"],
        )
        count_map = {}
        for r in rows:
            if not r.get("lead_id"):
                continue
            lid = r["lead_id"][0]
            cnt = r.get("id_count", r.get("__count", 0)) or 0
            count_map[lid] = cnt
        sums = Finance.read_group(
            domain=[("lead_id", "in", lead_ids), ("state", "=", "confirmed")],
            fields=["lead_id", "signed_amount:sum"],
            groupby=["lead_id"],
        )
        sum_map = {r["lead_id"][0]: (r.get("signed_amount") or 0.0)
                   for r in sums if r.get("lead_id")}
        for lead in self:
            if lead.id:
                lead.finance_count = count_map.get(lead.id, 0)
                lead.finance_amount_sum = sum_map.get(lead.id, 0.0)

    def action_open_finance_lead(self):
        self.ensure_one()
        action = self.env.ref("cc_finance.action_cc_finance").read()[0]
        action["domain"] = [("lead_id", "=", self.id)]
        action["context"] = {
            "default_lead_id": self.id,
            "default_employee_id": self.usta_id.id or False,
            "search_default_last_30": 1,
        }
        return action

    # ==== Service Number ====
    service_number = fields.Char(
        string="Service #",
        copy=False,
        readonly=True,
        index=True,
        default=False,
    )
    new_at = fields.Datetime(copy=False)

    _sql_constraints = [
        ("uniq_service_number", "unique(service_number)", "Service number must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("new_at", now)  # ✅ always set new_at
        leads = super(CrmLead, self).create(vals_list)

        for lead in leads.sudo():
            if not lead.service_number:
                num = lead._next_service_number_for_company(lead.company_id or self.env.company)
                lead.with_context(skip_service_number=True).write({"service_number": num})
        return leads

    def _next_service_number_for_company(self, company):
        Seq = self.env["ir.sequence"].with_company(company).sudo().search(
            [("code", "=", SERVICE_SEQ_CODE)], limit=1
        )
        if not Seq:
            # global sequence (company=False)
            Seq = self.env["ir.sequence"].with_company(False).sudo().search(
                [("code", "=", SERVICE_SEQ_CODE)], limit=1
            )

        if not Seq:
            # endi hech qanday fallback yo'q, to'g'ridan-to'g'ri xato
            raise UserError(
                _(
                    "Service number sequence is not configured.\n"
                    "Please create an ir.sequence with code '%s'."
                )
                % SERVICE_SEQ_CODE
            )

        num = Seq.next_by_code(SERVICE_SEQ_CODE)
        if not num:
            raise UserError(
                _("Failed to generate a new service number from sequence '%s'.")
                % SERVICE_SEQ_CODE
            )

        return num

    
    def _get_client_phone_for_sms(self):
        self.ensure_one()
        phone = (
            self.phone
            or self.mobile
            or getattr(self, "partner_phone", False)
            or (self.partner_id and (self.partner_id.mobile or self.partner_id.phone))
        )
        phone = self._normalize_phone(phone or "")
        if not phone:
            return False
        phone12 = phone[-9:]
        phone12 = f"998{phone12}"
        return phone12

    def _build_warranty_register_text(self):
        self.ensure_one()

        service_no = self.service_number or "-"
        usta = self.usta_id
        usta_name = (usta and usta.name) or "-"

        usta_phone = ""
        if usta:
            u_phone = (
                getattr(usta, "mobile", False)
                or getattr(usta, "phone", False)
                or getattr(usta, "work_phone", False)
                or ""
            )
            usta_phone = self._normalize_phone(u_phone)
            if len(usta_phone) == 12 and usta_phone.startswith("998"):
                usta_phone = "+" + usta_phone

        menejer = (
            (self.user_id and self.user_id.name)
            or (self.create_uid and self.create_uid.name)
            or (self.write_uid and self.write_uid.name)
            or ""
        )

        # ✅ EXACT approved text format (including "olindi.Mutaxassisimiz" without space)
        text = (
            f"Assalomu alaykum! Murojaatingiz №{service_no} raqam bilan VOLNA SERVIS markazida ro‘yxatga olindi."
            f"Mutaxassisimiz 4 ish kuni ichida muammoni bartaraf qiladi. "
            f"Servis usta: {usta_name} {usta_phone}, Menejer: {menejer}."
        )

        return text

    def _send_warranty_register_sms(self):
        """Murojaat ro'yxatdan o'tganda mijozga sms yuborish (Eskiz orqali)."""
        ICP = self.env["ir.config_parameter"].sudo()
        use_odoo_sms = (ICP.get_param("crm_rating_sms.use_odoo_sms") or "0") == "1"
        use_my_eskiz = (ICP.get_param("crm_rating_sms.use_my_eskiz") or "0").lower() in ("1", "true", "yes")
        debug = self._is_debug()

        for lead in self:
            if lead.warranty_sms_sent:
                continue

            phone12 = lead._get_client_phone_for_sms()
            if not phone12:
                lead.message_post(body=_("Warranty SMS: mijoz telefoni topilmadi."))
                continue

            text = lead._build_warranty_register_text()

            # --- faqat ichki note rejimi (debug/odoo sms) ---
            if use_odoo_sms:
                lead.message_post(body=_("Warranty SMS (note-only): %s -> %s") % (phone12, text))
                lead.warranty_sms_sent = True
                continue

            # --- my.eskiz.uz varianti (Bearer token bilan) ---
            if use_my_eskiz:
                base = (ICP.get_param("crm_rating_sms.my_eskiz_base") or "https://my.eskiz.uz/api").rstrip("/")
                url = f"{base}/message/sms/send"
                token = (ICP.get_param("crm_rating_sms.my_eskiz_token") or "").strip()
                sender = (ICP.get_param("crm_rating_sms.my_eskiz_from") or ICP.get_param("crm_rating_sms.sender") or "4546").strip()

                if not (token and sender):
                    msg = "Warranty SMS (my.eskiz): token yoki sender sozlanmagan."
                    lead.message_post(body=_(msg))
                    continue

                payload = {
                    "mobile_phone": phone12,
                    "message": text,
                    "from": sender,
                }
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

                try:
                    r = requests.post(url, json=payload, headers=headers, timeout=20)
                    js = {}
                    try:
                        js = r.json()
                    except Exception:
                        js = {"status": f"http {r.status_code}", "body": r.text}

                    status_str = str(js.get("status") or "").lower()
                    if r.status_code == 200 and status_str in ("success", "ok", "accepted", "waiting"):
                        lead.warranty_sms_sent = True
                        lead.message_post(
                            body=_("Warranty SMS yuborildi (my.eskiz): %s") % (phone12,)
                        )
                    else:
                        lead.message_post(
                            body=_("Warranty SMS (my.eskiz) yuborilmadi: %s") % (str(js)[:500],)
                        )
                except Exception as e:
                    lead.message_post(
                        body=_("Warranty SMS (my.eskiz) xatolik: %s") % (str(e)[:500],)
                    )
                continue

            # --- notify.eskiz.uz (eskiz_sms kutubxonasi) ---
            try:
                eskiz = self._eskiz_client()
                sender = ICP.get_param("crm_rating_sms.sender", "4546")
                callback = ICP.get_param("crm_rating_sms.callback_url") or None

                def _do_send():
                    return eskiz.send_sms(
                        phone12,
                        message=text,
                        from_whom=sender,
                        callback_url=callback,
                    )

                try:
                    resp = _do_send()
                except BadRequest:
                    # token eskirgan bo'lishi mumkin – yana bir marta urinib ko'ramiz
                    try:
                        eskiz.token.set("")
                    except Exception:
                        pass
                    resp = _do_send()

                resp_dict = {
                    "id": getattr(resp, "id", None),
                    "status": getattr(resp, "status", None),
                    "message": getattr(resp, "message", None),
                    "data": getattr(resp, "data", None),
                }
                status = str(resp_dict.get("status") or "").lower()
                msg_id = (
                    resp_dict.get("id")
                    or ((resp_dict.get("data") or {}) or {}).get("message_id")
                )
                ok = bool(msg_id) or status in ("ok", "success", "waiting", "accepted")

                if ok:
                    lead.warranty_sms_sent = True
                    lead.message_post(
                        body=_("Mijozga Service yaratildi SMS yuborildi (notify.eskiz)")
                    )
                else:
                    err = resp_dict.get("message") or resp_dict or "Unknown provider response"
                    lead.message_post(
                        body=_("Warranty SMS yuborilmadi: %s") % (str(err)[:500],)
                    )
            except Exception as e:
                lead.message_post(
                    body=_("Warranty SMS yuborilmadi (exception): %s") % (str(e)[:500],)
                )



    def write(self, vals):
        # 1) super
        res = super(CrmLead, self).write(vals)
        
        
        if "qayta_zayavka" in vals and vals.get("qayta_zayavka"):
            Finance = self.env["cc.finance"].sudo()
            for lead in self.sudo():
                fin = Finance.search([
                    ("lead_id", "=", lead.id),
                    ("state", "!=", "cancelled"),
                ])
                if fin:
                    fin.write({"state": "cancelled"})
                    lead.message_post(body=_("Qayta zayavka ON: mavjud finance yozuvlari CANCEL qilindi."))


        # 2) fill service # if missing
        if not self.env.context.get("skip_service_number"):
            for lead in self.sudo().filtered(lambda l: not l.service_number):
                num = lead._next_service_number_for_company(lead.company_id or self.env.company)
                lead.with_context(skip_service_number=True).write({"service_number": num})

        # 3) stage-based timeline; KPI NI ENDI TASDIQLANDI DA BERAMIZ
        if "stage_id" in vals:
            now = fields.Datetime.now()

            for lead in self.sudo():
                stage_name = (lead.stage_id.name or "").lower()
                updates = {}

                # ✅ Safety: if new_at is missing for any reason, set it ASAP
                if not lead.new_at:
                    updates["new_at"] = now

                is_new = any(k in stage_name for k in ("yangi", "new", "draft", "assigned"))
                is_accept = any(k in stage_name for k in ("qabul", "waiting", "kutil"))
                is_start = any(k in stage_name for k in ("jarayon", "progress"))
                is_finish = any(k in stage_name for k in ("yakun", "done", "finish"))
                is_confirm = any(k in stage_name for k in ("tasdiq", "confirm"))

                # NEW stage capture (only first time)
                if is_new and not lead.new_at:
                    updates["new_at"] = now

                # ACCEPT capture + section time New→Accept
                if is_accept and not lead.accept_at:
                    updates["accept_at"] = now
                    start_new = lead.new_at or updates.get("new_at") or lead.create_date
                    if start_new:
                        updates["new_to_accept_hours"] = round((now - start_new).total_seconds() / 3600.0, 2)

                # START capture + section time Accept→Start
                if is_start and not lead.start_at:
                    updates.setdefault("accept_at", lead.accept_at or now)  # keep accept if already exists
                    updates["start_at"] = now

                    a = lead.accept_at or updates.get("accept_at")
                    if a:
                        updates["accept_to_start_hours"] = round((now - a).total_seconds() / 3600.0, 2)

                    # also compute New→Start if you want (optional)

                # FINISH capture + section time Start→Finish + totals
                if is_finish:
                    if not lead.finish_at:
                        updates["finish_at"] = now

                    f = updates.get("finish_at") or lead.finish_at or now
                    s = lead.start_at or updates.get("start_at")
                    a = lead.accept_at or updates.get("accept_at")
                    n = lead.new_at or updates.get("new_at") or lead.create_date

                    if s:
                        updates["start_to_finish_hours"] = round((f - s).total_seconds() / 3600.0, 2)

                    # ✅ total New→Finish (this is what you wanted instead of accept/progress fallback)
                    if n:
                        updates["total_to_finish_hours"] = round((f - n).total_seconds() / 3600.0, 2)
                        updates["work_time_spent"] = updates["total_to_finish_hours"]  # keep your existing field meaningful

                if updates:
                    lead.with_context(skip_service_number=True).sudo().write(updates)


                if is_confirm:
                    # ensure finish exists before confirm timing
                    f = lead.finish_at or now
                    n = lead.new_at or lead.create_date

                    if lead.finish_at:
                        lead.sudo().write({
                            "finish_to_confirm_hours": round((now - f).total_seconds() / 3600.0, 2),
                            "total_to_confirm_hours": round((now - n).total_seconds() / 3600.0, 2) if n else 0.0,
                        })

                    # ✅ If qayta zayavka: do NOT give KPI or any bonus finance
                    if lead.finish_at and lead.qayta_zayavka:
                        lead.message_post(
                            body=_("Qayta zayavka ON: Tasdiqlashda KPI/bonus/finance hisoblanmadi."),
                            subtype_xmlid="mail.mt_note"
                        )
                    elif lead.finish_at:
                        self.env["cc.kpi.result"].sudo().upsert_time_from_lead(lead)
                        lead._apply_olov_bonus_if_applicable()

                # Warranty SMS block (keep as you already have)
                try:
                    leads_for_sms = self.sudo().filtered(
                        lambda l: not l.warranty_sms_sent
                        and l.service_number
                        and l.usta_id
                        and "qabul" in (l.stage_id.name or "").lower()
                    )
                    if leads_for_sms:
                        leads_for_sms._send_warranty_register_sms()
                except Exception:
                    pass


        return res

    contact_display = fields.Char(compute="_compute_contact_display", string="Kontakt nomi", store=False)

    @api.depends("partner_name","partner_id.display_name","contact_name","phone","mobile","email_from")
    def _compute_contact_display(self):
        for lead in self:
            v = (lead.partner_name or "").strip()
            if not v and lead.partner_id:
                v = (lead.partner_id.display_name or lead.partner_id.name or "").strip()
            if not v:
                v = (lead.contact_name or "").strip()
            if not v:
                v = (lead.phone or lead.mobile or lead.email_from or "").strip()
            lead.contact_display = v or "-"


    @api.onchange('partner_id', 'partner_name')
    def _onchange_partner_uzbek_title(self):
        """Quick-create paytida default nomni 'X ning murojaati'ga aylantiradi."""
        # faqat yangi yoki default nom bo'lsa o'zgartiramiz
        defaultish = False
        if (self.name or '').strip():
            low = self.name.strip().lower()
            # Odoo’ning defaultlari: "X's Opportunity" / "X's opportunity"
            defaultish = low.endswith("opportunity") or "opportunity" in low
        if not self.id and (not self.name or defaultish):
            who = (self.partner_name or (self.partner_id and self.partner_id.name) or "").strip()
            if who:
                # kerak bo'lsa yozuvdagi ' ning' oldidagi bo'shliqni saqlaymiz
                self.name = f"{who} ning murojati"
       
    voice_attachment_ids = fields.Many2many(
        "ir.attachment", "crm_lead_voice_rel", "lead_id", "attachment_id",
        string="Ovozli xabar(lar)",
        help="Audio fayllarni biriktiring (yoki chatterga yuklang)."
    )

    voice_gallery_html = fields.Html(
        string="Ovozlar preview",
        compute="_compute_voice_gallery_html",
        sanitize=False
    )

    @api.depends(
        "voice_attachment_ids", "voice_attachment_ids.mimetype",
        "message_attachment_count", "write_date"
    )
    def _compute_voice_gallery_html(self):
        Att = self.env["ir.attachment"].sudo()
        for rec in self:
            auds = (rec.voice_attachment_ids or self.env["ir.attachment"]).filtered(
                lambda a: (a.mimetype or "").startswith("audio/")
            )
            chatter_auds = Att.search([
                ("res_model", "=", "crm.lead"),
                ("res_id", "=", rec.id or 0),
                ("mimetype", "ilike", "audio")
            ])
            seen, ordered = set(), []
            for a in list(auds) + list(chatter_auds):
                if a.id not in seen:
                    seen.add(a.id); ordered.append(a)

            # Har doim ildiz <div> bo‘lsin:
            html = [
                """<style>
                .cl-audio-list{display:flex;flex-direction:column;gap:8px}
                .cl-audio-item{padding:8px;border:1px solid #e5e7eb;border-radius:8px;background:#fafafa}
                .cl-audio-name{font-size:12px;color:#475569;margin-bottom:4px;word-break:break-all}
                </style>""",
                '<div class="cl-audio-list">'
            ]
            if ordered:
                for att in ordered:
                    url = f"/web/content/{att.id}?download=false"
                    title = (att.name or "").replace('"', "&quot;")
                    html.append(
                        f'<div class="cl-audio-item">'
                        f'  <div class="cl-audio-name">{title}</div>'
                        f'  <audio controls preload="none" src="{url}"></audio>'
                        f'</div>'
                    )
            # bo‘sh bo‘lsa ham yopuvchi div bor
            html.append("</div>")
            rec.voice_gallery_html = "".join(html)


    def _map_partner_city_to_cc_region(self, partner):
        """partner.district_id (cc.region) yoki city/city_id bo'yicha region topadi."""
        Region = self.env["cc.region"].sudo()

        # 0) YANGI: agar partner.district_id bo'lsa – bevosita shu region
        if hasattr(partner, "district_id") and partner.district_id:
            return partner.district_id

        # 1) Agar boshqa joylarda res.city_id ishlatilayotgan bo'lsa – fallback
        if hasattr(partner, "city_id") and partner.city_id:
            return Region.search([
                ("name", "ilike", partner.city_id.name or ""),
                ("state_id", "=", partner.city_id.state_id.id or False),
            ], limit=1)

        # 2) Matnli city → cc.region
        city_name = (partner.city or "").strip()
        if city_name:
            dom = [("name", "ilike", city_name)]
            if partner.state_id:
                dom.append(("state_id", "=", partner.state_id.id))
            return Region.search(dom, limit=1)

        return self.env["cc.region"]

    @api.onchange("partner_id")
    def _onchange_partner_auto_geo(self):
        p = self.partner_id
        if not p:
            return

        # Telefon
        if not (self.phone or self.mobile):
            self.phone = p.mobile or p.phone

        # Davlat / Viloyat
        if p.country_id:
            self.country_id = p.country_id
        if p.state_id:
            self.state_id = p.state_id

        # Tuman: eng avval partner.district_id, bo'lmasa mapper
        if hasattr(p, "district_id") and p.district_id:
            self.region_id = p.district_id
        elif not self.region_id:
            reg = self._map_partner_city_to_cc_region(p)
            if reg:
                self.region_id = reg

        # Manzil
        if not self.street and p.street:
            self.street = p.street


    def _onchange_partner_id_values(self, partner_id):
        vals = super()._onchange_partner_id_values(partner_id)
        Partner = self.env["res.partner"].browse(partner_id)
        if not Partner.exists():
            return vals

        # Telefon
        if not self.phone and (Partner.mobile or Partner.phone):
            vals.setdefault("phone", Partner.mobile or Partner.phone)

        # Davlat / Viloyat
        if Partner.country_id:
            vals["country_id"] = Partner.country_id.id
        if Partner.state_id:
            vals["state_id"] = Partner.state_id.id

        # Tuman (cc.region): 1) district_id, 2) fallback mapper
        reg = False
        if hasattr(Partner, "district_id") and Partner.district_id:
            reg = Partner.district_id
        else:
            reg = self._map_partner_city_to_cc_region(Partner)

        if reg:
            vals["region_id"] = reg.id
            # Agar partner.state_id bilan mos kelmasa, xavfsizlik uchun tozalaymiz
            if Partner.state_id and reg.state_id and reg.state_id.id != Partner.state_id.id:
                vals["region_id"] = False

        # Manzil
        if Partner.street and not self.street:
            vals.setdefault("street", Partner.street)

        return vals


