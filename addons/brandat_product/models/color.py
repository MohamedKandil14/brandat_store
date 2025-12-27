from odoo import models, fields

class BrandatColor(models.Model):
    _name = 'brandat.color'
    _description = 'Product Color'

    name = fields.Char(string='Color Name', required=True)
    code = fields.Char(string='Code')
