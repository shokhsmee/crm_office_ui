from odoo import api, fields, models, _
from odoo.exceptions import UserError
from urllib.parse import quote_plus
import requests
from eskiz_sms import EskizSMS
from eskiz_sms.exceptions import BadRequest, InvalidCredentials

import logging

_logger = logging.getLogger(__name__)


class CrmLeadProductLine(models.Model):
    _name = "crm.lead.product.line"
    _description = "CRM Lead Product Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade")

    product_id = fields.Many2one(
        "product.product",
        string="Mahsulot",
        related="sync_line_id.product_id",
        store=True,        
        readonly=True,
    )
    description = fields.Text(string="Tavsif")
    quantity = fields.Float(string="Miqdor", default=1.0, digits="Product Unit of Measure", required=True)

    uom_id = fields.Many2one("uom.uom", string="O'lchov birligi",
                             related="product_id.uom_id", store=True, readonly=True)

    price_unit = fields.Monetary(string="Narx", required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", related="lead_id.currency_id", store=True, readonly=True)

    subtotal = fields.Monetary(string="Jami", compute="_compute_subtotal", store=True, currency_field="currency_id")

    sync_line_id = fields.Many2one(
        "product.sale.sync",
        string="Sotuv (Serial)",
        required=True,
        index=True,
    )
    # --- SALE INFO (from product.sale.sync) ---
    sale_date = fields.Datetime(string="Sotuv sanasi", related="sync_line_id.sale_date", store=False, readonly=True)
    warehouse_name = fields.Char(string="Dukon", related="sync_line_id.warehouse_name", store=False, readonly=True)
    salesperson_name = fields.Char(string="Sotuvchi", related="sync_line_id.salesperson_name", store=False, readonly=True)

    serial_name = fields.Char(string="Serial", related="sync_line_id.serial_name", store=False, readonly=True)
    # If sync_line_id has lot_id, you can show it too:
    lot_name = fields.Char(string="Lot", compute="_compute_lot_name", store=False, readonly=True)

    sold_qty = fields.Float(string="Sotilgan miqdor", related="sync_line_id.quantity", store=False, readonly=True)
    sold_price_unit = fields.Float(string="Sotuv narxi", related="sync_line_id.price_unit", store=False, readonly=True)

    sold_partner = fields.Char(string="Sotib olgan", compute="_compute_sold_partner", store=False, readonly=True)
    sold_phone = fields.Char(string="Telefon", compute="_compute_sold_partner", store=False, readonly=True)

    @api.depends("sync_line_id.lot_id", "sync_line_id.lot_id.name")
    def _compute_lot_name(self):
        for rec in self:
            rec.lot_name = rec.sync_line_id.lot_id.name if rec.sync_line_id and rec.sync_line_id.lot_id else False

    @api.depends("sync_line_id.partner_id", "sync_line_id.partner_id.phone", "sync_line_id.partner_id.mobile")
    def _compute_sold_partner(self):
        for rec in self:
            p = rec.sync_line_id.partner_id if rec.sync_line_id else False
            rec.sold_partner = p.name if p else False
            rec.sold_phone = (p.phone or p.mobile) if p else False


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

    @api.onchange("sync_line_id")
    def _onchange_sync_line_id(self):
        for line in self:
            if line.sync_line_id:
                # take sale price by default
                line.price_unit = line.sync_line_id.price_unit or line.product_id.list_price or 0.0
                if not line.quantity:
                    line.quantity = 1.0




from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmProductWork(models.Model):
    _name = "crmproduct_work"
    _description = "CRM Product Work (Take/Return)"
    _order = "create_date desc, id desc"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade", index=True)
    usta_id = fields.Many2one("cc.employee", required=True, ondelete="restrict", index=True)

    state = fields.Selection(
        [
            ("take", "Olib ketish"),
            ("return", "Qaytarish"),
        ],
        required=True,
        default="take",
        index=True,
    )

    note = fields.Char()
    tg_user_id = fields.Char(index=True)
    tg_chat_id = fields.Char()
    tg_message_id = fields.Char()


    @api.model
    def latest_state(self, lead_id, usta_id):
        rec = self.sudo().search(
            [("lead_id", "=", int(lead_id)), ("usta_id", "=", int(usta_id))],
            limit=1,
            order="create_date desc, id desc",
        )
        return rec.state if rec else False

    @api.model
    def create_take(self, lead_id, usta_id, tg_user_id=None, tg_chat_id=None, tg_message_id=None, note=None):
        lead = self.env["crm.lead"].sudo().browse(int(lead_id))
        if not lead.exists():
            raise UserError(_("Zayavka topilmadi."))

        vals = {
            "lead_id": int(lead_id),
            "usta_id": int(usta_id),
            "state": "take",
            "note": note or "",
            "tg_user_id": str(tg_user_id or ""),
            "tg_chat_id": str(tg_chat_id or ""),
            "tg_message_id": str(tg_message_id or ""),
        }
        rec = self.sudo().create(vals)

        return rec

    @api.model
    def create_return(self, lead_id, usta_id, tg_user_id=None, tg_chat_id=None, tg_message_id=None, note=None):
        lead = self.env["crm.lead"].sudo().browse(int(lead_id))
        if not lead.exists():
            raise UserError(_("Zayavka topilmadi."))

        vals = {
            "lead_id": int(lead_id),
            "usta_id": int(usta_id),
            "state": "return",
            "note": note or "",
            "tg_user_id": str(tg_user_id or ""),
            "tg_chat_id": str(tg_chat_id or ""),
            "tg_message_id": str(tg_message_id or ""),
        }
        rec = self.sudo().create(vals)

        return rec


from odoo import api, fields, models

class CrmLead(models.Model):
    _inherit = "crm.lead"

    prodwork_state = fields.Selection(
        [("take", "Olib ketdi"), ("return", "Qaytardi")],
        compute="_compute_prodwork_state",
        store=False,
    )

    @api.depends("usta_id")
    def _compute_prodwork_state(self):
        Work = self.env["crmproduct_work"].sudo()

        for lead in self:
            old = lead.prodwork_state  # may be False/None in compute context
            new = False

            if lead.id:
                domain = [("lead_id", "=", lead.id)]
                if lead.usta_id:
                    domain.append(("usta_id", "=", lead.usta_id.id))

                last = Work.search(domain, order="create_date desc, id desc", limit=1)

                if not last and lead.usta_id:
                    last = Work.search([("lead_id", "=", lead.id)],
                                       order="create_date desc, id desc", limit=1)

                new = last.state if last else False

            lead.prodwork_state = new

            # ✅ LOG (only when something actually changes)
            if old != new:
                _logger.warning(
                    "[PRODWORK_STATE] lead_id=%s service=%s usta_id=%s old=%s new=%s",
                    lead.id,
                    getattr(lead, "service_number", None),
                    lead.usta_id.id if lead.usta_id else None,
                    old,
                    new,
                )