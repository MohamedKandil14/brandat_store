from odoo import models, fields, api, tools
from datetime import datetime, timedelta

class BrandatSalesReport(models.Model):
    _name = 'brandat.sales.report'
    _description = 'Sales Report'
    _auto = False
    _order = 'date desc'
    
    date = fields.Date(string='التاريخ', readonly=True)
    store_id = fields.Many2one('brandat.store', string='الفرع', readonly=True)
    product_id = fields.Many2one('brandat.product', string='المنتج', readonly=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', readonly=True)
    color_id = fields.Many2one('brandat.color', string='اللون', readonly=True)
    quantity = fields.Integer(string='الكمية المباعة', readonly=True)
    price_unit = fields.Float(string='سعر الوحدة', readonly=True)
    price_total = fields.Float(string='الإجمالي', readonly=True)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancel', 'ملغية')
    ], string='الحالة', readonly=True)
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    sl.id as id,
                    DATE(s.date) as date,
                    s.store_id,
                    sl.product_id,
                    sl.size_id,
                    sl.color_id,
                    sl.quantity,
                    sl.price_unit,
                    sl.price_subtotal as price_total,
                    s.state
                FROM brandat_sale_line sl
                JOIN brandat_sale s ON sl.sale_id = s.id
                WHERE s.state = 'confirmed'
            )
        """ % self._table)


class BrandatStockReport(models.Model):
    _name = 'brandat.stock.report'
    _description = 'Stock Report'
    _auto = False
    
    store_id = fields.Many2one('brandat.store', string='الفرع', readonly=True)
    product_id = fields.Many2one('brandat.product', string='المنتج', readonly=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', readonly=True)
    color_id = fields.Many2one('brandat.color', string='اللون', readonly=True)
    quantity = fields.Integer(string='الكمية المتاحة', readonly=True)
    product_value = fields.Float(string='قيمة المخزون', readonly=True)
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    st.id as id,
                    st.store_id,
                    st.product_id,
                    st.size_id,
                    st.color_id,
                    st.quantity,
                    (st.quantity * p.price) as product_value
                FROM brandat_stock st
                JOIN brandat_product p ON st.product_id = p.id
            )
        """ % self._table)


class BrandatReportWizard(models.TransientModel):
    _name = 'brandat.report.wizard'
    _description = 'Report Wizard'
    
    report_type = fields.Selection([
        ('daily', 'تقرير يومي'),
        ('monthly', 'تقرير شهري'),
        ('yearly', 'تقرير سنوي'),
        ('custom', 'فترة مخصصة'),
    ], string='نوع التقرير', required=True, default='daily')
    
    date_from = fields.Date(string='من تاريخ', default=fields.Date.today)
    date_to = fields.Date(string='إلى تاريخ', default=fields.Date.today)
    store_id = fields.Many2one('brandat.store', string='الفرع')
    product_id = fields.Many2one('brandat.product', string='المنتج')
    
    @api.onchange('report_type')
    def _onchange_report_type(self):
        today = fields.Date.today()
        if self.report_type == 'daily':
            self.date_from = today
            self.date_to = today
        elif self.report_type == 'monthly':
            self.date_from = today.replace(day=1)
            self.date_to = today
        elif self.report_type == 'yearly':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today
    
    def action_generate_report(self):
        self.ensure_one()
        
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        
        if self.store_id:
            domain.append(('store_id', '=', self.store_id.id))
        
        if self.product_id:
            domain.append(('product_id', '=', self.product_id.id))
        
        return {
            'name': 'تقرير المبيعات',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sales.report',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
            'context': {'search_default_group_by_date': 1}
        }
    
    def action_stock_report(self):
        self.ensure_one()
        
        domain = []
        
        if self.store_id:
            domain.append(('store_id', '=', self.store_id.id))
        
        if self.product_id:
            domain.append(('product_id', '=', self.product_id.id))
        
        return {
            'name': 'تقرير المخزون',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.stock.report',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
        }
    
    def action_top_products(self):
        self.ensure_one()
        
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        
        if self.store_id:
            domain.append(('store_id', '=', self.store_id.id))
        
        return {
            'name': 'أكثر المنتجات مبيعاً',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sales.report',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
            'context': {
                'search_default_group_by_product': 1,
                'pivot_measures': ['quantity', 'price_total']
            }
        }
    
    def action_store_performance(self):
        self.ensure_one()
        
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        
        return {
            'name': 'أداء الفروع',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sales.report',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
            'context': {
                'search_default_group_by_store': 1,
                'pivot_measures': ['quantity', 'price_total']
            }
        }