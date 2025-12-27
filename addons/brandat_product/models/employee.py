# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BrandatEmployee(models.Model):
    _name = 'brandat.employee'
    _description = 'Brandat Employee'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='اسم الموظف', required=True, tracking=True)
    code = fields.Char(string='كود الموظف', required=True, copy=False, readonly=True, default='New')
    user_id = fields.Many2one('res.users', string='حساب المستخدم', tracking=True)
    
    # معلومات شخصية
    phone = fields.Char(string='رقم الهاتف', tracking=True)
    email = fields.Char(string='البريد الإلكتروني', tracking=True)
    address = fields.Text(string='العنوان')
    national_id = fields.Char(string='الرقم القومي')
    birth_date = fields.Date(string='تاريخ الميلاد')
    
    # معلومات الوظيفة
    store_id = fields.Many2one('brandat.store', string='الفرع', required=True, tracking=True)
    role = fields.Selection([
        ('cashier', 'كاشير'),
        ('manager', 'مدير فرع'),
        ('owner', 'مالك'),
    ], string='الوظيفة', required=True, default='cashier', tracking=True)
    
    hire_date = fields.Date(string='تاريخ التعيين', default=fields.Date.today, tracking=True)
    salary = fields.Float(string='الراتب الأساسي', tracking=True)
    commission_rate = fields.Float(string='نسبة العمولة (%)', default=0.0, tracking=True)
    
    # الحالة
    state = fields.Selection([
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('suspended', 'موقوف'),
    ], string='الحالة', default='active', tracking=True)
    
    # الصورة
    image = fields.Binary(string='الصورة')
    
    # الإحصائيات
    total_sales = fields.Float(string='إجمالي المبيعات', compute='_compute_statistics', store=True)
    total_commission = fields.Float(string='إجمالي العمولات', compute='_compute_statistics', store=True)
    sale_count = fields.Integer(string='عدد الفواتير', compute='_compute_statistics', store=True)
    
    # ملاحظات
    notes = fields.Text(string='ملاحظات')

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('brandat.employee') or 'New'
        return super(BrandatEmployee, self).create(vals)

    @api.depends('name')
    def _compute_statistics(self):
        for record in self:
            sales = self.env['brandat.sale'].search([
                ('employee_id', '=', record.id),
                ('state', '=', 'confirmed')
            ])
            record.total_sales = sum(sales.mapped('amount_total'))
            record.sale_count = len(sales)
            record.total_commission = record.total_sales * (record.commission_rate / 100)

    def action_view_sales(self):
        return {
            'name': 'مبيعات الموظف',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sale',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }

    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        for record in self:
            if record.commission_rate < 0 or record.commission_rate > 100:
                raise ValidationError('نسبة العمولة يجب أن تكون بين 0 و 100')


# سجل الحضور والانصراف
class BrandatAttendance(models.Model):
    _name = 'brandat.attendance'
    _description = 'Brandat Employee Attendance'
    _order = 'check_in desc'

    employee_id = fields.Many2one('brandat.employee', string='الموظف', required=True, ondelete='cascade')
    check_in = fields.Datetime(string='وقت الحضور', required=True, default=fields.Datetime.now)
    check_out = fields.Datetime(string='وقت الانصراف')
    worked_hours = fields.Float(string='ساعات العمل', compute='_compute_worked_hours', store=True)
    notes = fields.Text(string='ملاحظات')

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for record in self:
            if record.check_in and record.check_out:
                delta = record.check_out - record.check_in
                record.worked_hours = delta.total_seconds() / 3600
            else:
                record.worked_hours = 0

    def action_check_out(self):
        self.write({'check_out': fields.Datetime.now()})