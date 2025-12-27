from odoo import models, fields

class BrandatProduct(models.Model):
    _name = 'brandat.product'
    _description = 'Brandat Product'
    
    name = fields.Char(string='اسم المنتج', required=True)
    code = fields.Char(string='كود المنتج')
    price = fields.Float(string='السعر', required=True, default=0.0)
    description = fields.Text(string='الوصف')