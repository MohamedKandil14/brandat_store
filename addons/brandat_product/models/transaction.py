# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BrandatTransaction(models.Model):
    _name = 'brandat.transaction'
    _description = 'Brandat Financial Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char(string='رقم المعاملة', required=True, default='New', readonly=True)
    treasury_id = fields.Many2one('brandat.treasury', string='الخزينة', tracking=True)
    
    transaction_type = fields.Selection([
        ('income', 'إيراد'),
        ('expense', 'مصروف'),
        ('transfer', 'تحويل'),
    ], string='نوع المعاملة', required=True, tracking=True)
    
    category_id = fields.Many2one('brandat.transaction.category', string='التصنيف', tracking=True)
    
    amount = fields.Float(string='المبلغ', required=True, tracking=True)
    date = fields.Datetime(string='التاريخ', default=fields.Datetime.now, required=True, tracking=True)
    
    # المرجع
    reference_model = fields.Selection([
        ('brandat.sale', 'فاتورة مبيعات'),
        ('brandat.purchase', 'فاتورة شراء'),
        ('brandat.payment', 'دفعة'),
        ('brandat.expense', 'مصروف'),
    ], string='نوع المرجع')
    reference_id = fields.Integer(string='رقم المرجع')
    
    # التفاصيل
    description = fields.Text(string='الوصف', required=True)
    employee_id = fields.Many2one('brandat.employee', string='الموظف', tracking=True)
    
    # طريقة الدفع
    payment_method = fields.Selection([
        ('cash', 'نقدي'),
        ('card', 'بطاقة'),
        ('bank', 'تحويل بنكي'),
        ('other', 'أخرى'),
    ], string='طريقة الدفع', default='cash', tracking=True)
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancel', 'ملغية'),
    ], default='draft', string='الحالة', tracking=True)
    
    notes = fields.Text(string='ملاحظات')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.transaction') or 'New'
        return super(BrandatTransaction, self).create(vals)
    
    def action_confirm(self):
        """تأكيد المعاملة"""
        for transaction in self:
            if transaction.state == 'confirmed':
                raise ValidationError('المعاملة مؤكدة بالفعل!')
            
            # التحقق من وجود خزينة مفتوحة
            if transaction.treasury_id and transaction.treasury_id.state != 'open':
                raise ValidationError('لا يمكن تأكيد معاملة على خزينة مغلقة!')
            
            transaction.write({'state': 'confirmed'})
    
    def action_cancel(self):
        """إلغاء المعاملة"""
        self.write({'state': 'cancel'})
    
    def action_draft(self):
        """إرجاع لمسودة"""
        self.write({'state': 'draft'})


class BrandatTransactionCategory(models.Model):
    _name = 'brandat.transaction.category'
    _description = 'Transaction Category'
    
    name = fields.Char(string='اسم التصنيف', required=True)
    type = fields.Selection([
        ('income', 'إيراد'),
        ('expense', 'مصروف'),
    ], string='النوع', required=True)
    
    code = fields.Char(string='الكود')
    active = fields.Boolean(string='نشط', default=True)
    notes = fields.Text(string='ملاحظات')