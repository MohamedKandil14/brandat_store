from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class BrandatSaleReturn(models.Model):
    _name = 'brandat.sale.return'
    _description = 'Sale Return'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'
    
    name = fields.Char(string='رقم المرتجع', default='New', readonly=True)
    sale_id = fields.Many2one('brandat.sale', string='الفاتورة الأصلية', required=True, 
                              domain="[('state', '=', 'confirmed')]", tracking=True)
    date = fields.Datetime(string='تاريخ المرتجع', default=fields.Datetime.now, required=True, tracking=True)
    store_id = fields.Many2one('brandat.store', string='الفرع', related='sale_id.store_id', store=True, readonly=True)
    customer_id = fields.Many2one('brandat.customer', string='العميل', related='sale_id.customer_id', store=True, readonly=True)
    
    return_type = fields.Selection([
        ('return', 'مرتجع (استرجاع مالي)'),
        ('exchange', 'استبدال'),
    ], string='نوع العملية', required=True, default='return', tracking=True)
    
    line_ids = fields.One2many('brandat.sale.return.line', 'return_id', string='المنتجات المرتجعة')
    exchange_line_ids = fields.One2many('brandat.sale.return.exchange', 'return_id', string='المنتجات البديلة')
    
    reason = fields.Selection([
        ('defect', 'عيب في المنتج'),
        ('wrong_size', 'مقاس خاطئ'),
        ('wrong_color', 'لون خاطئ'),
        ('not_as_described', 'غير مطابق للوصف'),
        ('customer_changed_mind', 'العميل غير رأيه'),
        ('other', 'أخرى'),
    ], string='سبب المرتجع', required=True, tracking=True)
    
    reason_details = fields.Text(string='تفاصيل السبب')
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('done', 'مكتمل'),
        ('cancel', 'ملغي')
    ], default='draft', string='الحالة', tracking=True)
    
    # الحسابات
    return_amount = fields.Float(string='مبلغ المرتجع', compute='_compute_amounts', store=True)
    exchange_amount = fields.Float(string='مبلغ الاستبدال', compute='_compute_amounts', store=True)
    difference_amount = fields.Float(string='الفرق', compute='_compute_amounts', store=True)
    
    # الملاحظات
    notes = fields.Text(string='ملاحظات')
    
    # التواريخ
    days_since_sale = fields.Integer(string='عدد الأيام من البيع', compute='_compute_days_since_sale')
    can_return = fields.Boolean(string='يمكن الإرجاع', compute='_compute_can_return')
    return_period_days = fields.Integer(string='مدة الإرجاع (أيام)', default=7)
    
    @api.depends('sale_id.date', 'date')
    def _compute_days_since_sale(self):
        for record in self:
            if record.sale_id and record.sale_id.date:
                delta = record.date - record.sale_id.date
                record.days_since_sale = delta.days
            else:
                record.days_since_sale = 0
    
    @api.depends('days_since_sale', 'return_period_days')
    def _compute_can_return(self):
        for record in self:
            record.can_return = record.days_since_sale <= record.return_period_days
    
    @api.depends('line_ids.return_amount', 'exchange_line_ids.exchange_amount')
    def _compute_amounts(self):
        for record in self:
            record.return_amount = sum(line.return_amount for line in record.line_ids)
            record.exchange_amount = sum(line.exchange_amount for line in record.exchange_line_ids)
            record.difference_amount = record.exchange_amount - record.return_amount
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.sale.return') or 'New'
        return super().create(vals)
    
    @api.onchange('sale_id')
    def _onchange_sale_id(self):
        """ملء المنتجات المرتجعة من الفاتورة"""
        if self.sale_id:
            # حذف الأسطر القديمة
            self.line_ids = [(5, 0, 0)]
            
            # إنشاء أسطر جديدة من الفاتورة
            lines = []
            for sale_line in self.sale_id.line_ids:
                lines.append((0, 0, {
                    'sale_line_id': sale_line.id,
                    'product_id': sale_line.product_id.id,
                    'size_id': sale_line.size_id.id,
                    'color_id': sale_line.color_id.id,
                    'quantity_sold': sale_line.quantity,
                    'quantity_return': 0,
                    'price_unit': sale_line.price_unit,
                }))
            self.line_ids = lines
    
    def action_approve(self):
        """اعتماد المرتجع"""
        self.ensure_one()
        
        if not self.line_ids.filtered(lambda l: l.quantity_return > 0):
            raise ValidationError('يجب تحديد كمية مرتجعة لمنتج واحد على الأقل!')
        
        if not self.can_return:
            raise ValidationError(f'تجاوزت مدة الإرجاع المسموحة ({self.return_period_days} أيام)!')
        
        # التحقق من الكميات
        for line in self.line_ids:
            if line.quantity_return > line.quantity_sold:
                raise ValidationError(
                    f'الكمية المرتجعة ({line.quantity_return}) أكبر من الكمية المباعة ({line.quantity_sold}) '
                    f'للمنتج: {line.product_id.name}'
                )
        
        self.state = 'approved'
        
        self.message_post(
            body=f'تم اعتماد المرتجع رقم {self.name}',
            subject='اعتماد المرتجع'
        )
    
    def action_complete(self):
        """إكمال المرتجع - إرجاع للمخزون"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise ValidationError('يجب اعتماد المرتجع أولاً!')
        
        # إرجاع المنتجات المرتجعة للمخزون
        for line in self.line_ids.filtered(lambda l: l.quantity_return > 0):
            stock = self.env['brandat.stock'].search([
                ('store_id', '=', self.store_id.id),
                ('product_id', '=', line.product_id.id),
                ('size_id', '=', line.size_id.id),
                ('color_id', '=', line.color_id.id),
            ], limit=1)
            
            if stock:
                stock.quantity += line.quantity_return
            else:
                self.env['brandat.stock'].create({
                    'store_id': self.store_id.id,
                    'product_id': line.product_id.id,
                    'size_id': line.size_id.id,
                    'color_id': line.color_id.id,
                    'quantity': line.quantity_return,
                })
        
        # في حالة الاستبدال، خصم المنتجات البديلة من المخزون
        if self.return_type == 'exchange':
            for line in self.exchange_line_ids:
                stock = self.env['brandat.stock'].search([
                    ('store_id', '=', self.store_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('size_id', '=', line.size_id.id),
                    ('color_id', '=', line.color_id.id),
                ], limit=1)
                
                if not stock or stock.quantity < line.quantity:
                    raise ValidationError(
                        f'الكمية غير متاحة في المخزون للمنتج البديل: {line.product_id.name}\n'
                        f'المتاح: {stock.quantity if stock else 0}\n'
                        f'المطلوب: {line.quantity}'
                    )
                
                stock.quantity -= line.quantity
        
        self.state = 'done'
        
        message = f'تم إكمال {dict(self._fields["return_type"].selection)[self.return_type]} رقم {self.name}\n'
        if self.return_type == 'return':
            message += f'المبلغ المسترجع: {self.return_amount:.2f} جنيه'
        else:
            if self.difference_amount > 0:
                message += f'المبلغ المطلوب من العميل: {self.difference_amount:.2f} جنيه'
            elif self.difference_amount < 0:
                message += f'المبلغ المسترجع للعميل: {abs(self.difference_amount):.2f} جنيه'
            else:
                message += 'استبدال متساوي القيمة'
        
        self.message_post(
            body=message,
            subject='إكمال المرتجع'
        )
    
    def action_cancel(self):
        if self.state == 'done':
            raise ValidationError('لا يمكن إلغاء مرتجع مكتمل!')
        self.state = 'cancel'
    
    def action_draft(self):
        self.state = 'draft'


class BrandatSaleReturnLine(models.Model):
    _name = 'brandat.sale.return.line'
    _description = 'Sale Return Line'
    
    return_id = fields.Many2one('brandat.sale.return', string='المرتجع', ondelete='cascade', required=True)
    sale_line_id = fields.Many2one('brandat.sale.line', string='سطر الفاتورة', required=True)
    
    product_id = fields.Many2one('brandat.product', string='المنتج', required=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', required=True)
    color_id = fields.Many2one('brandat.color', string='اللون', required=True)
    
    quantity_sold = fields.Integer(string='الكمية المباعة', readonly=True)
    quantity_return = fields.Integer(string='الكمية المرتجعة', default=0)
    
    price_unit = fields.Float(string='سعر الوحدة', readonly=True)
    return_amount = fields.Float(string='مبلغ المرتجع', compute='_compute_return_amount', store=True)
    
    @api.depends('quantity_return', 'price_unit')
    def _compute_return_amount(self):
        for line in self:
            line.return_amount = line.quantity_return * line.price_unit
    
    @api.constrains('quantity_return', 'quantity_sold')
    def _check_quantity(self):
        for line in self:
            if line.quantity_return < 0:
                raise ValidationError('الكمية المرتجعة يجب أن تكون أكبر من أو تساوي صفر!')
            if line.quantity_return > line.quantity_sold:
                raise ValidationError(
                    f'الكمية المرتجعة ({line.quantity_return}) أكبر من الكمية المباعة ({line.quantity_sold})!'
                )


class BrandatSaleReturnExchange(models.Model):
    _name = 'brandat.sale.return.exchange'
    _description = 'Sale Return Exchange Line'
    
    return_id = fields.Many2one('brandat.sale.return', string='المرتجع', ondelete='cascade', required=True)
    
    product_id = fields.Many2one('brandat.product', string='المنتج البديل', required=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', required=True)
    color_id = fields.Many2one('brandat.color', string='اللون', required=True)
    
    quantity = fields.Integer(string='الكمية', default=1, required=True)
    price_unit = fields.Float(string='سعر الوحدة', required=True)
    exchange_amount = fields.Float(string='مبلغ الاستبدال', compute='_compute_exchange_amount', store=True)
    
    @api.depends('quantity', 'price_unit')
    def _compute_exchange_amount(self):
        for line in self:
            line.exchange_amount = line.quantity * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.price


# إضافة حقول للفاتورة الأصلية
class BrandatSale(models.Model):
    _inherit = 'brandat.sale'
    
    return_ids = fields.One2many('brandat.sale.return', 'sale_id', string='المرتجعات')
    return_count = fields.Integer(string='عدد المرتجعات', compute='_compute_return_count')
    has_returns = fields.Boolean(string='يوجد مرتجعات', compute='_compute_return_count')
    
    @api.depends('return_ids')
    def _compute_return_count(self):
        for sale in self:
            sale.return_count = len(sale.return_ids)
            sale.has_returns = sale.return_count > 0
    
    def action_view_returns(self):
        self.ensure_one()
        return {
            'name': 'المرتجعات',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sale.return',
            'view_mode': 'list,form',
            'domain': [('sale_id', '=', self.id)],
            'context': {'default_sale_id': self.id}
        }
    
    def action_create_return(self):
        """إنشاء مرتجع جديد"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise ValidationError('يمكن إنشاء مرتجع فقط للفواتير المؤكدة!')
        
        return {
            'name': 'إنشاء مرتجع',
            'type': 'ir.actions.act_window',
            'res_model': 'brandat.sale.return',
            'view_mode': 'form',
            'context': {'default_sale_id': self.id},
            'target': 'current',
        }