# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api

def post_init_backfill_service_numbers(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Lead = env["crm.lead"].sudo()
    seq = env["ir.sequence"]
    code = "crm.lead.service.number"

    # Only Servis leads missing a number (keep as-is if you only number Servis)
    to_fix = Lead.search([("category_type", "=", "servis"), ("service_number", "=", False)])
    for lead in to_fix:
        lead.service_number = seq.next_by_code(code)
