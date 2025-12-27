# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BrandatExpense(models.Model):
    _name = 'brandat.expense'
    _description = 'Brandat Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char(string='رقم المصروف', required=True, default='New', readonly=True)
    
    expense_type = fields.Selection([
        ('fixed', 'ثابت'),
        ('variable', 'متغير'),
    ], string='نوع المصروف', required=True, default='variable', tracking=True)
    
    category_id = fields.Many2one('brandat.expense.category', string='التصنيف', required=True, tracking=True)
    
    amount = fields.Float(string='المبلغ', required=True, tracking=True)
    date = fields.Date(string='التاريخ', default=fields.Date.today, required=True, tracking=True)
    
    store_id = fields.Many2one('brandat.store', string='الفرع', tracking=True)
    treasury_id = fields.Many2one('brandat.treasury', string='الخزينة', tracking=True)
    employee_id = fields.Many2one('brandat.employee', string='الموظف', tracking=True)
    
    # التفاصيل
    description = fields.Text(string='الوصف', required=True)
    
    # المرفقات
    attachment_ids = fields.Many2many('ir.attachment', string='المرفقات')
    
    # طريقة الدفع
    payment_method = fields.Selection([
        ('cash', 'نقدي'),
        ('card', 'بطاقة'),
        ('bank', 'تحويل بنكي'),
        ('check', 'شيك'),
    ], string='طريقة الدفع', default='cash', tracking=True)
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكد'),
        ('paid', 'مدفوع'),
        ('cancel', 'ملغي'),
    ], default='draft', string='الحالة', tracking=True)
    
    notes = fields.Text(string='ملاحظات')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.expense') or 'New'
        return super(BrandatExpense, self).create(vals)
    
    def action_confirm(self):
        """تأكيد المصروف"""
        for expense in self:
            if expense.state == 'confirmed':
                raise ValidationError('المصروف مؤكد بالفعل!')
            
            expense.write({'state': 'confirmed'})
    
    def action_pay(self):
        """دفع المصروف"""
        for expense in self:
            if expense.state != 'confirmed':
                raise ValidationError('يجب تأكيد المصروف أولاً!')
            
            # إنشاء معاملة مالية
            transaction_vals = {
                'treasury_id': expense.treasury_id.id if expense.treasury_id else False,
                'transaction_type': 'expense',
                'category_id': self.env['brandat.transaction.category'].search([
                    ('name', '=', expense.category_id.name)
                ], limit=1).id,
                'amount': expense.amount,
                'date': fields.Datetime.now(),
                'description': f'مصروف - {expense.description}',
                'reference_model': 'brandat.expense',
                'reference_id': expense.id,
                'payment_method': expense.payment_method,
                'employee_id': expense.employee_id.id if expense.employee_id else False,
                'state': 'confirmed',
            }
            
            self.env['brandat.transaction'].create(transaction_vals)
            
            expense.write({'state': 'paid'})
    
    def action_cancel(self):
        """إلغاء المصروف"""
        self.write({'state': 'cancel'})
    
    def action_draft(self):
        """إرجاع لمسودة"""
        self.write({'state': 'draft'})


class BrandatExpenseCategory(models.Model):
    _name = 'brandat.expense.category'
    _description = 'Expense Category'
    
    name = fields.Char(string='اسم التصنيف', required=True)
    code = fields.Char(string='الكود')
    
    expense_type = fields.Selection([
        ('fixed', 'ثابت'),
        ('variable', 'متغير'),
    ], string='النوع', default='variable')
    
    active = fields.Boolean(string='نشط', default=True)
    notes = fields.Text(string='ملاحظات')