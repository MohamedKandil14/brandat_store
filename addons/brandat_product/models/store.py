from odoo import models, fields

class BrandatStore(models.Model):
    _name = 'brandat.store'
    _description = 'Brandat Store'
    
    name = fields.Char(string='اسم الفرع', required=True)
    code = fields.Char(string='كود الفرع')
    address = fields.Text(string='العنوان')