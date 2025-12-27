# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class BrandatAccountReport(models.TransientModel):
    _name = 'brandat.account.report'
    _description = 'Brandat Account Report'
    
    # الفترة
    date_from = fields.Date(string='من تاريخ', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='إلى تاريخ', required=True, default=fields.Date.today)
    
    # الفلاتر
    store_id = fields.Many2one('brandat.store', string='الفرع')
    report_type = fields.Selection([
        ('profit_loss', 'الأرباح والخسائر'),
        ('treasury', 'حركة الخزينة'),
        ('debts', 'تقرير الديون'),
        ('expenses', 'تقرير المصروفات'),
    ], string='نوع التقرير', required=True, default='profit_loss')
    
    def action_print_report(self):
        """طباعة التقرير"""
        if self.report_type == 'profit_loss':
            return self.env.ref('brandat_product.action_report_profit_loss').report_action(self)
        elif self.report_type == 'treasury':
            return self.env.ref('brandat_product.action_report_treasury').report_action(self)
        elif self.report_type == 'debts':
            return self.env.ref('brandat_product.action_report_debts').report_action(self)
        elif self.report_type == 'expenses':
            return self.env.ref('brandat_product.action_report_expenses').report_action(self)
    
    def get_profit_loss_data(self):
        """حساب الأرباح والخسائر"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'confirmed'),
        ]
        
        if self.store_id:
            domain.append(('store_id', '=', self.store_id.id))
        
        # المبيعات
        sales = self.env['brandat.sale'].search(domain)
        total_sales = sum(sales.mapped('amount_total'))
        
        # المشتريات (تكلفة البضاعة)
        purchases = self.env['brandat.purchase'].search(domain)
        total_purchases = sum(purchases.mapped('amount_total'))
        
        # المصروفات
        expense_domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'paid'),
        ]
        if self.store_id:
            expense_domain.append(('store_id', '=', self.store_id.id))
        
        expenses = self.env['brandat.expense'].search(expense_domain)
        total_expenses = sum(expenses.mapped('amount'))
        
        # الحسابات
        gross_profit = total_sales - total_purchases  # الربح الإجمالي
        net_profit = gross_profit - total_expenses     # الربح الصافي
        profit_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0
        
        return {
            'total_sales': total_sales,
            'total_purchases': total_purchases,
            'gross_profit': gross_profit,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'store_name': self.store_id.name if self.store_id else 'جميع الفروع',
        }
    
    def get_treasury_data(self):
        """بيانات حركة الخزينة"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        
        if self.store_id:
            domain.append(('store_id', '=', self.store_id.id))
        
        treasuries = self.env['brandat.treasury'].search(domain)
        
        data = []
        for treasury in treasuries:
            data.append({
                'name': treasury.name,
                'date': treasury.date,
                'opening_balance': treasury.opening_balance,
                'total_income': treasury.total_income,
                'total_expense': treasury.total_expense,
                'closing_balance': treasury.closing_balance,
                'state': treasury.state,
            })
        
        return data
    
    def get_debts_data(self):
        """تقرير الديون"""
        # ديون العملاء
        customers = self.env['brandat.customer'].search([])
        customer_debts = []
        
        for customer in customers:
            sales = customer.sale_ids.filtered(lambda s: s.state == 'confirmed')
            total_sales = sum(sales.mapped('amount_total'))
            
            payments = self.env['brandat.payment'].search([
                ('customer_id', '=', customer.id),
                ('payment_type', '=', 'customer'),
                ('state', '=', 'confirmed'),
            ])
            total_payments = sum(payments.mapped('amount'))
            
            debt = total_sales - total_payments
            
            if debt > 0:
                customer_debts.append({
                    'name': customer.name,
                    'phone': customer.phone,
                    'total_sales': total_sales,
                    'total_payments': total_payments,
                    'debt': debt,
                })
        
        # ديون الموردين
        suppliers = self.env['brandat.supplier'].search([])
        supplier_debts = []
        
        for supplier in suppliers:
            purchases = supplier.purchase_ids.filtered(lambda p: p.state == 'confirmed')
            total_purchases = sum(purchases.mapped('amount_total'))
            
            payments = self.env['brandat.payment'].search([
                ('supplier_id', '=', supplier.id),
                ('payment_type', '=', 'supplier'),
                ('state', '=', 'confirmed'),
            ])
            total_payments = sum(payments.mapped('amount'))
            
            debt = total_purchases - total_payments
            
            if debt > 0:
                supplier_debts.append({
                    'name': supplier.name,
                    'phone': supplier.phone,
                    'total_purchases': total_purchases,
                    'total_payments': total_payments,
                    'debt': debt,
                })
        
        return {
            'customer_debts': customer_debts,
            'supplier_debts': supplier_debts,
            'total_customer_debts': sum([d['debt'] for d in customer_debts]),
            'total_supplier_debts': sum([d['debt'] for d in supplier_debts]),
        }