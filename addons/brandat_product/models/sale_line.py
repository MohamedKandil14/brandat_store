from odoo import models, fields, api

class BrandatSaleLine(models.Model):
    _name = 'brandat.sale.line'
    _description = 'Brandat Sale Line'
    
    sale_id = fields.Many2one('brandat.sale', string='الفاتورة', ondelete='cascade', required=True)
    product_id = fields.Many2one('brandat.product', string='المنتج', required=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', required=True)
    color_id = fields.Many2one('brandat.color', string='اللون', required=True)
    quantity = fields.Integer(string='الكمية', default=1, required=True)
    price_unit = fields.Float(string='سعر الوحدة', required=True)
    price_subtotal = fields.Float(string='الإجمالي', compute='_compute_subtotal', store=True)
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.price