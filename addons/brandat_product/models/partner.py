from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class BrandatCustomer(models.Model):
    _name = 'brandat.customer'
    _description = 'Brandat Customer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    name = fields.Char(string='اسم العميل', required=True, tracking=True)
    code = fields.Char(string='كود العميل', readonly=True, copy=False)
    phone = fields.Char(string='رقم الهاتف', tracking=True)
    mobile = fields.Char(string='رقم الموبايل', tracking=True)
    email = fields.Char(string='البريد الإلكتروني', tracking=True)
    address = fields.Text(string='العنوان')
    
    customer_type = fields.Selection([
        ('regular', 'عادي'),
        ('vip', 'VIP'),
        ('wholesale', 'جملة'),
    ], string='نوع العميل', default='regular', required=True, tracking=True)
    
    # نقاط الولاء
    loyalty_points = fields.Float(string='نقاط الولاء', compute='_compute_loyalty_points', store=True)
    total_purchases = fields.Float(string='إجمالي المشتريات', compute='_compute_total_purchases', store=True)
    purchase_count = fields.Integer(string='عدد الفواتير', compute='_compute_purchase_count')
    
    # الخصومات
    discount_percentage = fields.Float(string='نسبة الخصم %', default=0.0)
    
    # العلاقات
    sale_ids = fields.One2many('brandat.sale', 'partner_id', string='الفواتير')
    
    # الحالة
    active = fields.Boolean(string='نشط', default=True)
    notes = fields.Text(string='ملاحظات')
    
    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New' or not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('brandat.customer') or 'New'
        return super().create(vals)
    
    @api.depends('sale_ids.amount_total', 'sale_ids.state')
    def _compute_total_purchases(self):
        for customer in self:
            confirmed_sales = customer.sale_ids.filtered(lambda s: s.state == 'confirmed')
            customer.total_purchases = sum(confirmed_sales.mapped('amount_total'))
    
    @api.depends('total_purchases')
    def _compute_loyalty_points(self):
        # كل 100 جنيه = 1 نقطة
        for customer in self:
            customer.loyalty_points = customer.total_purchases / 100
    
    def _compute_purchase_count(self):
        for customer in self:
            customer.purchase_count = len(customer.sale_ids.filtered(lambda s: s.state == 'confirmed'))
    
    def action_view_sales(self):
        self.ensure_one()
        return {
            'name': 'فواتير العميل',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sale',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id}
        }


class BrandatSupplier(models.Model):
    _name = 'brandat.supplier'
    _description = 'Brandat Supplier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    name = fields.Char(string='اسم المورد', required=True, tracking=True)
    code = fields.Char(string='كود المورد', readonly=True, copy=False)
    phone = fields.Char(string='رقم الهاتف', tracking=True)
    mobile = fields.Char(string='رقم الموبايل', tracking=True)
    email = fields.Char(string='البريد الإلكتروني', tracking=True)
    address = fields.Text(string='العنوان')
    
    # معلومات مالية
    credit_limit = fields.Float(string='حد الائتمان')
    payment_terms = fields.Char(string='شروط الدفع')
    
    # معلومات إضافية
    company_name = fields.Char(string='اسم الشركة')
    tax_number = fields.Char(string='الرقم الضريبي')
    
    # العلاقات
    purchase_ids = fields.One2many('brandat.purchase', 'supplier_id', string='فواتير الشراء')
    purchase_count = fields.Integer(string='عدد الفواتير', compute='_compute_purchase_count')
    total_purchases = fields.Float(string='إجمالي المشتريات', compute='_compute_total_purchases')
    
    # الحالة
    active = fields.Boolean(string='نشط', default=True)
    notes = fields.Text(string='ملاحظات')
    
    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New' or not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('brandat.supplier') or 'New'
        return super().create(vals)
    
    def _compute_purchase_count(self):
        for supplier in self:
            supplier.purchase_count = len(supplier.purchase_ids.filtered(lambda p: p.state == 'confirmed'))
    
    @api.depends('purchase_ids.amount_total', 'purchase_ids.state')
    def _compute_total_purchases(self):
        for supplier in self:
            confirmed_purchases = supplier.purchase_ids.filtered(lambda p: p.state == 'confirmed')
            supplier.total_purchases = sum(confirmed_purchases.mapped('amount_total'))
    
    def action_view_purchases(self):
        self.ensure_one()
        return {
            'name': 'فواتير المورد',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.purchase',
            'view_mode': 'list,form',
            'domain': [('supplier_id', '=', self.id)],
            'context': {'default_supplier_id': self.id}
        }


class BrandatPurchase(models.Model):
    _name = 'brandat.purchase'
    _description = 'Brandat Purchase'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'
    
    name = fields.Char(string='رقم فاتورة الشراء', default='New', readonly=True)
    supplier_id = fields.Many2one('brandat.supplier', string='المورد', required=True, tracking=True)
    date = fields.Datetime(string='تاريخ الفاتورة', default=fields.Datetime.now, required=True, tracking=True)
    store_id = fields.Many2one('brandat.store', string='الفرع', required=True, tracking=True)
    
    line_ids = fields.One2many('brandat.purchase.line', 'purchase_id', string='المنتجات')
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancel', 'ملغية')
    ], default='draft', string='الحالة', tracking=True)
    
    amount_total = fields.Float(string='الإجمالي', compute='_compute_amount_total', store=True)
    notes = fields.Text(string='ملاحظات')
    
    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for purchase in self:
            purchase.amount_total = sum(line.price_subtotal for line in purchase.line_ids)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.purchase') or 'New'
        return super().create(vals)
    
    def action_confirm(self):
        for purchase in self:
            if not purchase.line_ids:
                raise ValidationError('لا يمكن تأكيد فاتورة شراء بدون منتجات!')
            
            # إضافة المنتجات للمخزون
            for line in purchase.line_ids:
                stock = self.env['brandat.stock'].search([
                    ('store_id', '=', purchase.store_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('size_id', '=', line.size_id.id),
                    ('color_id', '=', line.color_id.id),
                ], limit=1)
                
                if stock:
                    stock.quantity += line.quantity
                else:
                    self.env['brandat.stock'].create({
                        'store_id': purchase.store_id.id,
                        'product_id': line.product_id.id,
                        'size_id': line.size_id.id,
                        'color_id': line.color_id.id,
                        'quantity': line.quantity,
                    })
            
            purchase.state = 'confirmed'
    
    def action_cancel(self):
        self.state = 'cancel'
    
    def action_draft(self):
        self.state = 'draft'


class BrandatPurchaseLine(models.Model):
    _name = 'brandat.purchase.line'
    _description = 'Brandat Purchase Line'
    
    purchase_id = fields.Many2one('brandat.purchase', string='فاتورة الشراء', ondelete='cascade', required=True)
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