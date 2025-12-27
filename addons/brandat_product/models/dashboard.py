from odoo import models, fields, api
from datetime import datetime, timedelta
from collections import defaultdict

class BrandatDashboard(models.Model):
    _name = 'brandat.dashboard'
    _description = 'Brandat Dashboard'
    
    name = fields.Char(string='Dashboard', default='Brandat Dashboard')
    
    # مبيعات اليوم
    today_sales = fields.Float(string='مبيعات اليوم', compute='_compute_today_sales')
    today_sales_count = fields.Integer(string='عدد فواتير اليوم', compute='_compute_today_sales')
    
    # مبيعات الأسبوع
    week_sales = fields.Float(string='مبيعات الأسبوع', compute='_compute_week_sales')
    week_sales_count = fields.Integer(string='عدد فواتير الأسبوع', compute='_compute_week_sales')
    
    # مبيعات الشهر
    month_sales = fields.Float(string='مبيعات الشهر', compute='_compute_month_sales')
    month_sales_count = fields.Integer(string='عدد فواتير الشهر', compute='_compute_month_sales')
    
    # مقارنات
    yesterday_sales = fields.Float(string='مبيعات أمس', compute='_compute_yesterday_sales')
    sales_growth = fields.Float(string='نسبة النمو %', compute='_compute_sales_growth')
    
    # المخزون
    low_stock_count = fields.Integer(string='منتجات منخفضة', compute='_compute_stock_alerts')
    out_stock_count = fields.Integer(string='منتجات نفذت', compute='_compute_stock_alerts')
    
    # العملاء
    new_customers_today = fields.Integer(string='عملاء جدد اليوم', compute='_compute_customers')
    total_customers = fields.Integer(string='إجمالي العملاء', compute='_compute_customers')
    
    # المرتجعات
    today_returns = fields.Integer(string='مرتجعات اليوم', compute='_compute_returns')
    week_returns = fields.Integer(string='مرتجعات الأسبوع', compute='_compute_returns')
    
    @api.depends()
    def _compute_today_sales(self):
        for rec in self:
            today = fields.Date.today()
            sales = self.env['brandat.sale'].search([
                ('date', '>=', datetime.combine(today, datetime.min.time())),
                ('date', '<=', datetime.combine(today, datetime.max.time())),
                ('state', '=', 'confirmed')
            ])
            rec.today_sales = sum(sales.mapped('amount_total'))
            rec.today_sales_count = len(sales)
    
    @api.depends()
    def _compute_yesterday_sales(self):
        for rec in self:
            yesterday = fields.Date.today() - timedelta(days=1)
            sales = self.env['brandat.sale'].search([
                ('date', '>=', datetime.combine(yesterday, datetime.min.time())),
                ('date', '<=', datetime.combine(yesterday, datetime.max.time())),
                ('state', '=', 'confirmed')
            ])
            rec.yesterday_sales = sum(sales.mapped('amount_total'))
    
    @api.depends('today_sales', 'yesterday_sales')
    def _compute_sales_growth(self):
        for rec in self:
            if rec.yesterday_sales > 0:
                rec.sales_growth = ((rec.today_sales - rec.yesterday_sales) / rec.yesterday_sales) * 100
            else:
                rec.sales_growth = 100.0 if rec.today_sales > 0 else 0.0
    
    @api.depends()
    def _compute_week_sales(self):
        for rec in self:
            week_start = fields.Date.today() - timedelta(days=7)
            sales = self.env['brandat.sale'].search([
                ('date', '>=', datetime.combine(week_start, datetime.min.time())),
                ('state', '=', 'confirmed')
            ])
            rec.week_sales = sum(sales.mapped('amount_total'))
            rec.week_sales_count = len(sales)
    
    @api.depends()
    def _compute_month_sales(self):
        for rec in self:
            month_start = fields.Date.today().replace(day=1)
            sales = self.env['brandat.sale'].search([
                ('date', '>=', datetime.combine(month_start, datetime.min.time())),
                ('state', '=', 'confirmed')
            ])
            rec.month_sales = sum(sales.mapped('amount_total'))
            rec.month_sales_count = len(sales)
    
    @api.depends()
    def _compute_stock_alerts(self):
        for rec in self:
            stocks = self.env['brandat.stock'].search([])
            rec.low_stock_count = len(stocks.filtered(lambda s: s.state == 'low'))
            rec.out_stock_count = len(stocks.filtered(lambda s: s.state == 'out'))
    
    @api.depends()
    def _compute_customers(self):
        for rec in self:
            today = fields.Date.today()
            rec.new_customers_today = self.env['brandat.customer'].search_count([
                ('create_date', '>=', datetime.combine(today, datetime.min.time())),
                ('create_date', '<=', datetime.combine(today, datetime.max.time())),
            ])
            rec.total_customers = self.env['brandat.customer'].search_count([])
    
    @api.depends()
    def _compute_returns(self):
        for rec in self:
            today = fields.Date.today()
            week_start = today - timedelta(days=7)
            
            rec.today_returns = self.env['brandat.sale.return'].search_count([
                ('date', '>=', datetime.combine(today, datetime.min.time())),
                ('date', '<=', datetime.combine(today, datetime.max.time())),
            ])
            
            rec.week_returns = self.env['brandat.sale.return'].search_count([
                ('date', '>=', datetime.combine(week_start, datetime.min.time())),
            ])
    
    def get_sales_chart_data(self, period='week'):
        """بيانات رسم المبيعات"""
        if period == 'week':
            days = 7
        elif period == 'month':
            days = 30
        else:
            days = 7
        
        data = []
        labels = []
        
        for i in range(days - 1, -1, -1):
            date = fields.Date.today() - timedelta(days=i)
            sales = self.env['brandat.sale'].search([
                ('date', '>=', datetime.combine(date, datetime.min.time())),
                ('date', '<=', datetime.combine(date, datetime.max.time())),
                ('state', '=', 'confirmed')
            ])
            
            total = sum(sales.mapped('amount_total'))
            data.append(total)
            labels.append(date.strftime('%d/%m'))
        
        return {'labels': labels, 'data': data}
    
    def get_top_products(self, limit=10):
        """أعلى المنتجات مبيعاً"""
        month_start = fields.Date.today().replace(day=1)
        
        sale_lines = self.env['brandat.sale.line'].search([
            ('sale_id.date', '>=', datetime.combine(month_start, datetime.min.time())),
            ('sale_id.state', '=', 'confirmed')
        ])
        
        products = defaultdict(lambda: {'quantity': 0, 'amount': 0})
        
        for line in sale_lines:
            key = line.product_id.id
            products[key]['name'] = line.product_id.name
            products[key]['quantity'] += line.quantity
            products[key]['amount'] += line.price_subtotal
        
        sorted_products = sorted(products.items(), key=lambda x: x[1]['amount'], reverse=True)[:limit]
        
        return [
            {
                'name': item[1]['name'],
                'quantity': item[1]['quantity'],
                'amount': item[1]['amount']
            }
            for item in sorted_products
        ]
    
    def get_store_performance(self):
        """أداء الفروع"""
        month_start = fields.Date.today().replace(day=1)
        
        stores = self.env['brandat.store'].search([])
        result = []
        
        for store in stores:
            sales = self.env['brandat.sale'].search([
                ('store_id', '=', store.id),
                ('date', '>=', datetime.combine(month_start, datetime.min.time())),
                ('state', '=', 'confirmed')
            ])
            
            result.append({
                'name': store.name,
                'sales_count': len(sales),
                'total_amount': sum(sales.mapped('amount_total'))
            })
        
        return sorted(result, key=lambda x: x['total_amount'], reverse=True)
    
    def get_alerts(self):
        """التنبيهات والإشعارات"""
        alerts = []
        
        # تنبيهات المخزون المنخفض
        low_stocks = self.env['brandat.stock'].search([('state', '=', 'low')])
        if low_stocks:
            alerts.append({
                'type': 'warning',
                'icon': 'fa-exclamation-triangle',
                'title': 'مخزون منخفض',
                'message': f'{len(low_stocks)} منتج وصل للحد الأدنى',
                'action': 'brandat.stock'
            })
        
        # تنبيهات المخزون النافذ
        out_stocks = self.env['brandat.stock'].search([('state', '=', 'out')])
        if out_stocks:
            alerts.append({
                'type': 'danger',
                'icon': 'fa-times-circle',
                'title': 'مخزون نفذ',
                'message': f'{len(out_stocks)} منتج نفذ من المخزون',
                'action': 'brandat.stock'
            })
        
        # المرتجعات المعلقة
        pending_returns = self.env['brandat.sale.return'].search_count([('state', '=', 'approved')])
        if pending_returns:
            alerts.append({
                'type': 'info',
                'icon': 'fa-undo',
                'title': 'مرتجعات معلقة',
                'message': f'{pending_returns} مرتجع في انتظار الإكمال',
                'action': 'brandat.sale.return'
            })
        
        # عملاء جدد
        today = fields.Date.today()
        new_customers = self.env['brandat.customer'].search_count([
            ('create_date', '>=', datetime.combine(today, datetime.min.time()))
        ])
        if new_customers:
            alerts.append({
                'type': 'success',
                'icon': 'fa-user-plus',
                'title': 'عملاء جدد',
                'message': f'{new_customers} عميل جديد انضم اليوم',
                'action': 'brandat.customer'
            })
        
        return alerts