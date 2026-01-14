# -*- coding: utf-8 -*-
from odoo import fields, models

class CrmStage(models.Model):
    _inherit = "crm.stage"

    color_hex = fields.Char(string="Fon rangi (HEX)", default="#3498db", help="Masalan: #3498db")
    text_color_hex = fields.Char(string="Matn rangi (HEX)", default="#ffffff", help="Masalan: #ffffff")
