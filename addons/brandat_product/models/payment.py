# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BrandatPayment(models.Model):
    _name = 'brandat.payment'
    _description = 'Brandat Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char(string='رقم الدفعة', required=True, default='New', readonly=True)
    
    payment_type = fields.Selection([
        ('customer', 'دفعة من عميل'),
        ('supplier', 'دفعة لمورد'),
    ], string='نوع الدفعة', required=True, tracking=True)
    
    partner_id = fields.Many2one('res.partner', string='الطرف', tracking=True)
    customer_id = fields.Many2one('brandat.customer', string='العميل', tracking=True)
    supplier_id = fields.Many2one('brandat.supplier', string='المورد', tracking=True)
    
    amount = fields.Float(string='المبلغ', required=True, tracking=True)
    date = fields.Datetime(string='التاريخ', default=fields.Datetime.now, required=True, tracking=True)
    
    # المرجع
    sale_id = fields.Many2one('brandat.sale', string='فاتورة المبيعات')
    purchase_id = fields.Many2one('brandat.purchase', string='فاتورة الشراء')
    
    # الخزينة
    treasury_id = fields.Many2one('brandat.treasury', string='الخزينة', tracking=True)
    
    # طريقة الدفع
    payment_method = fields.Selection([
        ('cash', 'نقدي'),
        ('card', 'بطاقة'),
        ('bank', 'تحويل بنكي'),
        ('check', 'شيك'),
        ('other', 'أخرى'),
    ], string='طريقة الدفع', default='cash', required=True, tracking=True)
    
    # معلومات إضافية
    reference = fields.Char(string='المرجع')
    notes = fields.Text(string='ملاحظات')
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancel', 'ملغية'),
    ], default='draft', string='الحالة', tracking=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.payment') or 'New'
        return super(BrandatPayment, self).create(vals)
    
    def action_confirm(self):
        """تأكيد الدفعة"""
        for payment in self:
            if payment.state == 'confirmed':
                raise ValidationError('الدفعة مؤكدة بالفعل!')
            
            # إنشاء معاملة مالية
            transaction_vals = {
                'treasury_id': payment.treasury_id.id if payment.treasury_id else False,
                'transaction_type': 'income' if payment.payment_type == 'customer' else 'expense',
                'amount': payment.amount,
                'date': payment.date,
                'description': f'دفعة - {payment.name}',
                'reference_model': 'brandat.payment',
                'reference_id': payment.id,
                'payment_method': payment.payment_method,
                'state': 'confirmed',
            }
            
            self.env['brandat.transaction'].create(transaction_vals)
            
            payment.write({'state': 'confirmed'})
    
    def action_cancel(self):
        """إلغاء الدفعة"""
        # حذف المعاملة المالية المرتبطة
        transactions = self.env['brandat.transaction'].search([
            ('reference_model', '=', 'brandat.payment'),
            ('reference_id', '=', self.id),
        ])
        transactions.unlink()
        
        self.write({'state': 'cancel'})
    
    def action_draft(self):
        """إرجاع لمسودة"""
        self.write({'state': 'draft'})
    
    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        """تنظيف الحقول عند تغيير نوع الدفعة"""
        if self.payment_type == 'customer':
            self.supplier_id = False
        else:
            self.customer_id = False