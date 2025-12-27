from odoo import models, fields

class BrandatStock(models.Model):
    _name = 'brandat.stock'
    _description = 'Brandat Stock'

    product_id = fields.Many2one('brandat.product', string='Product', required=True)
    size_id = fields.Many2one('brandat.size', string='Size', required=True)
    color_id = fields.Many2one('brandat.color', string='Color', required=True)
    store_id = fields.Many2one('brandat.store', string='Store', required=True)
    quantity = fields.Integer(string='Quantity', default=0)
