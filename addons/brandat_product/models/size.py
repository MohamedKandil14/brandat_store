from odoo import models, fields

class BrandatSize(models.Model):
    _name = 'brandat.size'
    _description = 'Product Size'

    name = fields.Char(string='Size Name', required=True)
