# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class BrandatTreasury(models.Model):
    _name = 'brandat.treasury'
    _description = 'Brandat Treasury'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'
    
    name = fields.Char(string='رقم الخزينة', required=True, default='New', readonly=True)
    store_id = fields.Many2one('brandat.store', string='الفرع', required=True, tracking=True)
    employee_id = fields.Many2one('brandat.employee', string='المسؤول', tracking=True)
    date = fields.Date(string='التاريخ', default=fields.Date.today, required=True, tracking=True)
    
    # الأرصدة
    opening_balance = fields.Float(string='رصيد الافتتاح', tracking=True)
    closing_balance = fields.Float(string='رصيد الإقفال', compute='_compute_closing_balance', store=True)
    
    # الحركات
    total_income = fields.Float(string='إجمالي الإيرادات', compute='_compute_totals', store=True)
    total_expense = fields.Float(string='إجمالي المصروفات', compute='_compute_totals', store=True)
    total_sales = fields.Float(string='إجمالي المبيعات', compute='_compute_totals', store=True)
    total_purchases = fields.Float(string='إجمالي المشتريات', compute='_compute_totals', store=True)
    
    # العلاقات
    transaction_ids = fields.One2many('brandat.transaction', 'treasury_id', string='المعاملات')
    
    # الحالة
    state = fields.Selection([
        ('open', 'مفتوحة'),
        ('closed', 'مغلقة'),
    ], default='open', string='الحالة', tracking=True)
    
    notes = fields.Text(string='ملاحظات')
    
    # الفرق (للتسوية)
    difference = fields.Float(string='الفرق', compute='_compute_difference', store=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.treasury') or 'New'
        
        # الحصول على رصيد الإقفال من آخر خزينة مغلقة
        last_treasury = self.search([
            ('store_id', '=', vals.get('store_id')),
            ('state', '=', 'closed'),
        ], order='date desc', limit=1)
        
        if last_treasury:
            vals['opening_balance'] = last_treasury.closing_balance
        
        return super(BrandatTreasury, self).create(vals)
    
    @api.depends('transaction_ids.amount', 'transaction_ids.transaction_type')
    def _compute_totals(self):
        for treasury in self:
            # المبيعات
            sales = self.env['brandat.sale'].search([
                ('store_id', '=', treasury.store_id.id),
                ('date', '>=', treasury.date),
                ('date', '<', treasury.date + timedelta(days=1)),
                ('state', '=', 'confirmed'),
            ])
            treasury.total_sales = sum(sales.mapped('amount_total'))
            
            # المشتريات
            purchases = self.env['brandat.purchase'].search([
                ('store_id', '=', treasury.store_id.id),
                ('date', '>=', treasury.date),
                ('date', '<', treasury.date + timedelta(days=1)),
                ('state', '=', 'confirmed'),
            ])
            treasury.total_purchases = sum(purchases.mapped('amount_total'))
            
            # الإيرادات والمصروفات من المعاملات
            income_transactions = treasury.transaction_ids.filtered(lambda t: t.transaction_type == 'income')
            expense_transactions = treasury.transaction_ids.filtered(lambda t: t.transaction_type == 'expense')
            
            treasury.total_income = sum(income_transactions.mapped('amount')) + treasury.total_sales
            treasury.total_expense = sum(expense_transactions.mapped('amount')) + treasury.total_purchases
    
    @api.depends('opening_balance', 'total_income', 'total_expense')
    def _compute_closing_balance(self):
        for treasury in self:
            treasury.closing_balance = treasury.opening_balance + treasury.total_income - treasury.total_expense
    
    @api.depends('closing_balance')
    def _compute_difference(self):
        for treasury in self:
            # هنا ممكن نضيف حقل للرصيد الفعلي المعدود
            treasury.difference = 0.0
    
    def action_close(self):
        """إغلاق الخزينة"""
        if self.state == 'closed':
            raise ValidationError('الخزينة مغلقة بالفعل!')
        
        self.write({'state': 'closed'})
        
        # إنشاء معاملة إقفال
        self.env['brandat.transaction'].create({
            'treasury_id': self.id,
            'transaction_type': 'transfer',
            'amount': self.closing_balance,
            'description': f'إقفال الخزينة - {self.name}',
            'date': fields.Datetime.now(),
        })
    
    def action_reopen(self):
        """إعادة فتح الخزينة"""
        if self.state == 'open':
            raise ValidationError('الخزينة مفتوحة بالفعل!')
        
        # التحقق من عدم وجود خزينة أحدث
        newer_treasury = self.search([
            ('store_id', '=', self.store_id.id),
            ('date', '>', self.date),
        ], limit=1)
        
        if newer_treasury:
            raise ValidationError('لا يمكن إعادة فتح خزينة قديمة! يوجد خزائن أحدث.')
        
        self.write({'state': 'open'})
    
    def action_view_transactions(self):
        """عرض المعاملات"""
        return {
            'name': 'معاملات الخزينة',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.transaction',
            'view_mode': 'list,form',
            'domain': [('treasury_id', '=', self.id)],
            'context': {'default_treasury_id': self.id}
        }