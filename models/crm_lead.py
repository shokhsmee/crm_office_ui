# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

SERVICE_SEQ_CODE = "crm.lead.service.number"

class CrmLead(models.Model):
    _inherit = "crm.lead"

    category_type = fields.Selection(
        [("hamkorli","Hamkorli"),("shikoyat","Shikoyat"),("servis","Servis")],
        string="Murojaat turi", tracking=True,
    )

    usta_id = fields.Many2one("cc.employee", string="Usta", tracking=True)

    region_id = fields.Many2one("cc.region", string="Tuman (Region)",
                                domain="[('state_id','=',state_id)]", tracking=True)

    country_id = fields.Many2one(
        "res.country", string="Davlat",
        default=lambda self: self.env.ref("base.uz", raise_if_not_found=False)
            or self.env["res.country"].search([("code","=","UZ")], limit=1),
    )

    work_amount = fields.Monetary(string="Ish summasi")
    currency_id = fields.Many2one("res.currency",
                                  default=lambda self: self.env.company.currency_id)
    
    
    work_text = fields.Text(
        string="Ish tasnifi",
        tracking=True,
        help="Ishning qisqa tasnifi: masalan, diagnostika, kompressor almashtirish, drenaj tozalash va h.k."
    )
    
    
    accept_at = fields.Datetime(copy=False)
    start_at  = fields.Datetime(copy=False)
    finish_at = fields.Datetime(copy=False)

    work_time_spent = fields.Float(string="Ishga ketgan vaqt (soat)")
    work_time_pretty = fields.Char(
        string="Ishga ketgan vaqt",
        compute="_compute_work_time_pretty",
        store=False,
    )

    
    
    @api.depends("accept_at", "start_at", "finish_at", "write_date")
    def _compute_work_time_pretty(self):
        now = fields.Datetime.now()
        for lead in self:
            start = lead.accept_at or lead.start_at or lead.create_date
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
            if days:  parts.append(f"{days} kun")
            if hours: parts.append(f"{hours} soat")
            parts.append(f"{minutes} min")
            lead.work_time_pretty = " ".join(parts)
            
            
                
    @staticmethod
    def _humanize_seconds(seconds: float) -> str:
        total_minutes = int(round(seconds / 60.0))
        days, rem_min = divmod(total_minutes, 60 * 24)
        hours, minutes = divmod(rem_min, 60)
        parts = []
        if days:  parts.append(f"{days} kun")
        if hours: parts.append(f"{hours} soat")
        parts.append(f"{minutes} min")
        return " ".join(parts)
    

    photo_attachment_ids = fields.Many2many(
        "ir.attachment", "crm_lead_photo_rel", "lead_id", "attachment_id",
        string="Foto hisobot",
        help="Rasmlarni biriktiring (yoki chatterga yuklang).",
    )

    # ========== MAHSULOTLAR (Products) Section ==========
    product_line_ids = fields.One2many(
        "crm.lead.product.line", 
        "lead_id", 
        string="Mahsulotlar"
    )
    
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
    
    # ====================================================
    
    # Field to control Won button visibility
    show_won_button = fields.Boolean(
        string="Show Won Button",
        compute="_compute_show_won_button",
        store=False
    )
    
    @api.depends('stage_id', 'stage_id.name')
    def _compute_show_won_button(self):
        """Only show Won button in 'Ish yakunlandi' stage"""
        for lead in self:
            if lead.stage_id and lead.stage_id.name == 'Ish yakunlandi':
                lead.show_won_button = True
            else:
                lead.show_won_button = False
    
    def get_view(self, view_id=None, view_type='form', **options):
        """Override to add context for Won button visibility"""
        result = super(CrmLead, self).get_view(view_id, view_type, **options)
        
        # Add show_won_button field to the view if it's a form view
        if view_type == 'form' and self:
            for lead in self:
                if hasattr(lead, 'show_won_button'):
                    # This will be available in the view context
                    pass
        
        return result
    
    tg_card_chat_id = fields.Char("TG Card Chat")
    tg_card_msg_id  = fields.Char("TG Card Msg")
    
    @api.onchange("state_id", "region_id")
    def _onchange_location_filter_usta(self):
        """Filter usta based on selected region or state"""
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
        """Ensure region is selected before selecting usta"""
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
        """Validate that usta has access to the selected region"""
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
        action["domain"] = [("crm_service_id","=",self.id), ("move_type","=","out")]
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
            domain=[("lead_id", "in", lead_ids)],
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
            domain=[("lead_id", "in", lead_ids)],
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
        action["domain"] = [("lead_id","=",self.id)]
        action["context"] = {
            "default_lead_id": self.id,
            "default_employee_id": self.usta_id.id or False,
            "search_default_last_30": 1,
        }
        return action

    # Adding crm lead service Number
    service_number = fields.Char(
        string="Service #",
        copy=False,
        readonly=True,
        index=True,
        default=False,
    )

    _sql_constraints = [
        ("uniq_service_number", "unique(service_number)", "Service number must be unique."),
    ]

    def _next_service_number(self):
        return self.env["ir.sequence"].next_by_code(SERVICE_SEQ_CODE)

    @api.model_create_multi
    def create(self, vals_list):
        Seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("service_number"):
                try:
                    vals["service_number"] = Seq.next_by_code(SERVICE_SEQ_CODE) or "/"
                except Exception:
                    vals["service_number"] = "/"
        return super(CrmLead, self).create(vals_list)

    def write(self, vals):
        # 1) run base write
        res = super(CrmLead, self).write(vals)

        # 2) assign service number to any record still missing it
        if not self.env.context.get("skip_service_number"):
            to_assign = self.filtered(lambda l: not l.service_number)
            if to_assign:
                Seq = self.env["ir.sequence"].sudo()
                for lead in to_assign:
                    try:
                        num = Seq.next_by_code(SERVICE_SEQ_CODE) or "/"
                    except Exception:
                        num = "/"
                    lead.with_context(skip_service_number=True).sudo().write({"service_number": num})

        # 3) timeline updates based on stage name
        if "stage_id" in vals:
            now = fields.Datetime.now()
            for lead in self.sudo():
                stage_name = (lead.stage_id.name or "").lower()
                updates = {}

                # Qabul qilindi / Kutilmoqda / Waiting
                if any(k in stage_name for k in ("qabul", "waiting", "kutil")) and not lead.accept_at:
                    updates["accept_at"] = now

                # Jarayonda / In Progress
                if any(k in stage_name for k in ("jarayon", "progress")) and not lead.start_at:
                    # set accept_at if the lead skipped it
                    updates.setdefault("accept_at", now)
                    updates["start_at"] = now

                # Yakunlandi / Done / Finished
                if any(k in stage_name for k in ("yakun", "done", "finish")):
                    updates.setdefault("finish_at", now)
                    start_dt = lead.accept_at or lead.start_at or lead.create_date
                    if start_dt:
                        seconds = ((updates["finish_at"]) - start_dt).total_seconds()
                        updates["work_time_spent"] = round(seconds / 3600.0, 2)

                if updates:
                    # avoid re-triggering service-number part
                    lead.with_context(skip_service_number=True).sudo().write(updates)

        return res



class CrmLeadProductLine(models.Model):
    _name = "crm.lead.product.line"
    _description = "CRM Lead Product Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade")

    product_id = fields.Many2one(
        "product.product",
        string="Mahsulot",
        required=True,
        domain=[("sale_ok", "=", True)],
    )
    description = fields.Text(string="Tavsif")
    quantity = fields.Float(string="Miqdor", default=1.0, digits="Product Unit of Measure", required=True)

    uom_id = fields.Many2one("uom.uom", string="O'lchov birligi",
                             related="product_id.uom_id", store=True, readonly=True)

    price_unit = fields.Monetary(string="Narx", required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", related="lead_id.currency_id", store=True, readonly=True)

    subtotal = fields.Monetary(string="Jami", compute="_compute_subtotal", store=True, currency_field="currency_id")

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.quantity or 0.0) * (line.price_unit or 0.0)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.list_price
            if not self.description:
                self.description = self.product_id.name