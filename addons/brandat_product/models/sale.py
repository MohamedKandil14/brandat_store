# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BrandatSale(models.Model):
    _name = 'brandat.sale'
    _description = 'Brandat Sale'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'
    
    name = fields.Char(string='رقم الفاتورة', default='New', readonly=True)
    
    # استخدم res.partner بدل brandat.customer
    partner_id = fields.Many2one('res.partner', string='العميل', tracking=True)
    
    # أو أضف حقل جديد للعملاء الجدد
    customer_id = fields.Many2one('brandat.customer', string='عميل براندات', tracking=True)
    
    # حقل الموظف الجديد
    employee_id = fields.Many2one('brandat.employee', string='الموظف', tracking=True)
    
    date = fields.Datetime(string='تاريخ الفاتورة', default=fields.Datetime.now, required=True, tracking=True)
    store_id = fields.Many2one('brandat.store', string='الفرع', required=True, tracking=True)
    line_ids = fields.One2many('brandat.sale.line', 'sale_id', string='المنتجات')
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancel', 'ملغية')
    ], default='draft', string='الحالة', tracking=True)
    
    # الحسابات
    amount_untaxed = fields.Float(string='المبلغ قبل الخصم', compute='_compute_amounts', store=True)
    discount_type = fields.Selection([
        ('percentage', 'نسبة مئوية'),
        ('fixed', 'مبلغ ثابت'),
    ], string='نوع الخصم', default='percentage')
    discount_value = fields.Float(string='قيمة الخصم')
    discount_amount = fields.Float(string='مبلغ الخصم', compute='_compute_amounts', store=True)
    amount_total = fields.Float(string='الإجمالي النهائي', compute='_compute_amounts', store=True)
    
    # نقاط الولاء
    loyalty_points_earned = fields.Float(string='نقاط الولاء المكتسبة', compute='_compute_loyalty_points')
    loyalty_points_used = fields.Float(string='نقاط الولاء المستخدمة', default=0.0)
    
    # المرتجعات
    has_returns = fields.Boolean(string='لديه مرتجعات', compute='_compute_returns')
    return_count = fields.Integer(string='عدد المرتجعات', compute='_compute_returns')
    
    notes = fields.Text(string='ملاحظات')
    
    @api.depends('line_ids.price_subtotal', 'discount_type', 'discount_value', 'customer_id.discount_percentage')
    def _compute_amounts(self):
        for sale in self:
            amount_untaxed = sum(line.price_subtotal for line in sale.line_ids)
            sale.amount_untaxed = amount_untaxed
            
            # حساب الخصم
            discount = 0.0
            if sale.discount_type == 'percentage':
                discount = amount_untaxed * (sale.discount_value / 100)
            elif sale.discount_type == 'fixed':
                discount = sale.discount_value
            
            # إضافة خصم العميل
            if sale.customer_id and sale.customer_id.discount_percentage:
                customer_discount = amount_untaxed * (sale.customer_id.discount_percentage / 100)
                discount += customer_discount
            
            sale.discount_amount = discount
            sale.amount_total = amount_untaxed - discount
    
    @api.depends('amount_total')
    def _compute_loyalty_points(self):
        for sale in self:
            sale.loyalty_points_earned = sale.amount_total / 100
    
    def _compute_returns(self):
        for sale in self:
            returns = self.env['brandat.sale.return'].search([('sale_id', '=', sale.id)])
            sale.return_count = len(returns)
            sale.has_returns = bool(returns)
    
    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.customer_id and self.customer_id.discount_percentage:
            self.discount_type = 'percentage'
            self.discount_value = self.customer_id.discount_percentage
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.sale') or 'New'
        return super(BrandatSale, self).create(vals)
    
    def action_confirm(self):
        for sale in self:
            if not sale.line_ids:
                raise ValidationError('لا يمكن تأكيد فاتورة بدون منتجات!')
            
            for line in sale.line_ids:
                stock = self.env['brandat.stock'].search([
                    ('store_id', '=', sale.store_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('size_id', '=', line.size_id.id),
                    ('color_id', '=', line.color_id.id),
                ], limit=1)
                
                if not stock or stock.quantity < line.quantity:
                    raise ValidationError(
                        f'الكمية غير متاحة للمنتج: {line.product_id.name}\n'
                        f'المتاح: {stock.quantity if stock else 0}\n'
                        f'المطلوب: {line.quantity}'
                    )
                
                stock.quantity -= line.quantity
            
            # تحديث نقاط العميل
            if sale.customer_id:
                sale.customer_id.loyalty_points += sale.loyalty_points_earned
                sale.customer_id.loyalty_points -= sale.loyalty_points_used
            
            sale.state = 'confirmed'
    
    def action_cancel(self):
        self.state = 'cancel'
    
    def action_draft(self):
        self.state = 'draft'
    
    def action_print_invoice(self):
        return self.env.ref('brandat_product.action_report_brandat_sale').report_action(self)
    
    def action_send_email(self):
        template = self.env.ref('brandat_product.email_template_brandat_sale')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_composition_mode': 'comment',
                'default_template_id': template.id,
            }
        }
    
    def action_send_whatsapp(self):
        if not self.customer_id or not self.customer_id.phone:
            raise ValidationError('لا يوجد رقم هاتف للعميل!')
        
        message = f"فاتورة رقم: {self.name}\nالإجمالي: {self.amount_total} ج.م"
        phone = self.customer_id.phone.replace('+', '').replace(' ', '')
        url = f"https://wa.me/{phone}?text={message}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
    
    def action_create_return(self):
        return {
            'name': 'إنشاء مرتجع',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sale.return',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_id': self.id,
                'default_store_id': self.store_id.id,
                'default_customer_id': self.customer_id.id,
            }
        }
    
    def action_view_returns(self):
        return {
            'name': 'المرتجعات',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sale.return',
            'view_mode': 'list,form',
            'domain': [('sale_id', '=', self.id)],
        }


class BrandatSaleLine(models.Model):
    _name = 'brandat.sale.line'
    _description = 'Brandat Sale Line'
    
    sale_id = fields.Many2one('brandat.sale', string='الفاتورة', required=True, ondelete='cascade')
    product_id = fields.Many2one('brandat.product', string='المنتج', required=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', required=True)
    color_id = fields.Many2one('brandat.color', string='اللون', required=True)
    quantity = fields.Float(string='الكمية', default=1.0, required=True)
    price_unit = fields.Float(string='السعر', required=True)
    price_subtotal = fields.Float(string='المجموع', compute='_compute_subtotal', store=True)
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.price