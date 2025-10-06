# crm_office_ui/models/crm_lead_photo.py
from odoo import models, fields

class CrmLeadPhoto(models.Model):
    _name = "crm.lead.photo"
    _description = "Lead Photo Report"
    _order = "sequence, id"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade", index=True)
    name = fields.Char("Sarlavha")
    image_1920 = fields.Image("Rasm", required=True)
    note = fields.Char("Izoh")
    sequence = fields.Integer(default=10)
