from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class BrandatStockTransfer(models.Model):
    _name = 'brandat.stock.transfer'
    _description = 'Stock Transfer Between Stores'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'
    
    name = fields.Char(string='رقم التحويل', default='New', readonly=True)
    date = fields.Datetime(string='تاريخ التحويل', default=fields.Datetime.now, required=True, tracking=True)
    
    store_from_id = fields.Many2one('brandat.store', string='من فرع', required=True, tracking=True)
    store_to_id = fields.Many2one('brandat.store', string='إلى فرع', required=True, tracking=True)
    
    line_ids = fields.One2many('brandat.stock.transfer.line', 'transfer_id', string='المنتجات')
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكد'),
        ('done', 'مكتمل'),
        ('cancel', 'ملغي')
    ], default='draft', string='الحالة', tracking=True)
    
    notes = fields.Text(string='ملاحظات')
    
    @api.constrains('store_from_id', 'store_to_id')
    def _check_stores(self):
        for transfer in self:
            if transfer.store_from_id == transfer.store_to_id:
                raise ValidationError('لا يمكن التحويل من نفس الفرع إلى نفسه!')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.stock.transfer') or 'New'
        return super().create(vals)
    
    def action_confirm(self):
        """تأكيد التحويل - خصم من المخزون الأصلي"""
        for transfer in self:
            if not transfer.line_ids:
                raise ValidationError('لا يمكن تأكيد تحويل بدون منتجات!')
            
            for line in transfer.line_ids:
                # البحث عن المخزون في الفرع الأصلي
                stock_from = self.env['brandat.stock'].search([
                    ('store_id', '=', transfer.store_from_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('size_id', '=', line.size_id.id),
                    ('color_id', '=', line.color_id.id),
                ], limit=1)
                
                if not stock_from or stock_from.quantity < line.quantity:
                    raise ValidationError(
                        f'الكمية غير متاحة في {transfer.store_from_id.name}\n'
                        f'المنتج: {line.product_id.name}\n'
                        f'المتاح: {stock_from.quantity if stock_from else 0}\n'
                        f'المطلوب: {line.quantity}'
                    )
                
                # خصم من الفرع الأصلي
                stock_from.quantity -= line.quantity
            
            transfer.state = 'confirmed'
            
            # إرسال إشعار
            transfer.message_post(
                body=f'تم تأكيد التحويل من {transfer.store_from_id.name} إلى {transfer.store_to_id.name}',
                subject='تأكيد التحويل'
            )
    
    def action_done(self):
        """إكمال التحويل - إضافة للمخزون المستهدف"""
        for transfer in self:
            if transfer.state != 'confirmed':
                raise ValidationError('يجب تأكيد التحويل أولاً!')
            
            for line in transfer.line_ids:
                # البحث عن المخزون في الفرع المستهدف
                stock_to = self.env['brandat.stock'].search([
                    ('store_id', '=', transfer.store_to_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('size_id', '=', line.size_id.id),
                    ('color_id', '=', line.color_id.id),
                ], limit=1)
                
                if stock_to:
                    stock_to.quantity += line.quantity
                else:
                    # إنشاء سجل جديد
                    self.env['brandat.stock'].create({
                        'store_id': transfer.store_to_id.id,
                        'product_id': line.product_id.id,
                        'size_id': line.size_id.id,
                        'color_id': line.color_id.id,
                        'quantity': line.quantity,
                    })
            
            transfer.state = 'done'
            
            # إرسال إشعار
            transfer.message_post(
                body=f'تم إكمال التحويل إلى {transfer.store_to_id.name}',
                subject='إكمال التحويل'
            )
    
    def action_cancel(self):
        if self.state == 'done':
            raise ValidationError('لا يمكن إلغاء تحويل مكتمل!')
        self.state = 'cancel'
    
    def action_draft(self):
        self.state = 'draft'


class BrandatStockTransferLine(models.Model):
    _name = 'brandat.stock.transfer.line'
    _description = 'Stock Transfer Line'
    
    transfer_id = fields.Many2one('brandat.stock.transfer', string='التحويل', ondelete='cascade', required=True)
    product_id = fields.Many2one('brandat.product', string='المنتج', required=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', required=True)
    color_id = fields.Many2one('brandat.color', string='اللون', required=True)
    quantity = fields.Integer(string='الكمية', default=1, required=True)
    
    available_qty = fields.Integer(string='الكمية المتاحة', compute='_compute_available_qty')
    
    @api.depends('product_id', 'size_id', 'color_id', 'transfer_id.store_from_id')
    def _compute_available_qty(self):
        for line in self:
            if line.transfer_id.store_from_id and line.product_id and line.size_id and line.color_id:
                stock = self.env['brandat.stock'].search([
                    ('store_id', '=', line.transfer_id.store_from_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('size_id', '=', line.size_id.id),
                    ('color_id', '=', line.color_id.id),
                ], limit=1)
                line.available_qty = stock.quantity if stock else 0
            else:
                line.available_qty = 0


class BrandatStockInventory(models.Model):
    _name = 'brandat.stock.inventory'
    _description = 'Stock Inventory (جرد المخزون)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'
    
    name = fields.Char(string='رقم الجرد', default='New', readonly=True)
    date = fields.Datetime(string='تاريخ الجرد', default=fields.Datetime.now, required=True, tracking=True)
    store_id = fields.Many2one('brandat.store', string='الفرع', required=True, tracking=True)
    
    line_ids = fields.One2many('brandat.stock.inventory.line', 'inventory_id', string='المنتجات')
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('in_progress', 'جاري الجرد'),
        ('done', 'مكتمل'),
        ('cancel', 'ملغي')
    ], default='draft', string='الحالة', tracking=True)
    
    difference_count = fields.Integer(string='عدد الفروقات', compute='_compute_differences')
    notes = fields.Text(string='ملاحظات')
    
    @api.depends('line_ids.difference')
    def _compute_differences(self):
        for inventory in self:
            inventory.difference_count = len(inventory.line_ids.filtered(lambda l: l.difference != 0))
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('brandat.stock.inventory') or 'New'
        return super().create(vals)
    
    def action_start(self):
        """بدء الجرد - جلب المخزون الحالي"""
        self.ensure_one()
        
        # حذف الأسطر القديمة
        self.line_ids.unlink()
        
        # جلب كل المخزون في الفرع
        stocks = self.env['brandat.stock'].search([('store_id', '=', self.store_id.id)])
        
        # إنشاء أسطر الجرد
        for stock in stocks:
            self.env['brandat.stock.inventory.line'].create({
                'inventory_id': self.id,
                'product_id': stock.product_id.id,
                'size_id': stock.size_id.id,
                'color_id': stock.color_id.id,
                'theoretical_qty': stock.quantity,
                'real_qty': stock.quantity,  # سيتم تعديلها يدوياً
            })
        
        self.state = 'in_progress'
        
        self.message_post(
            body=f'تم بدء الجرد للفرع {self.store_id.name}',
            subject='بدء الجرد'
        )
    
    def action_validate(self):
        """تطبيق الجرد - تعديل المخزون"""
        self.ensure_one()
        
        if self.state != 'in_progress':
            raise ValidationError('يجب أن يكون الجرد في حالة "جاري الجرد"!')
        
        for line in self.line_ids:
            if line.difference != 0:
                stock = self.env['brandat.stock'].search([
                    ('store_id', '=', self.store_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('size_id', '=', line.size_id.id),
                    ('color_id', '=', line.color_id.id),
                ], limit=1)
                
                if stock:
                    stock.quantity = line.real_qty
        
        self.state = 'done'
        
        self.message_post(
            body=f'تم إكمال الجرد للفرع {self.store_id.name}\nعدد الفروقات: {self.difference_count}',
            subject='إكمال الجرد'
        )
    
    def action_cancel(self):
        if self.state == 'done':
            raise ValidationError('لا يمكن إلغاء جرد مكتمل!')
        self.state = 'cancel'


class BrandatStockInventoryLine(models.Model):
    _name = 'brandat.stock.inventory.line'
    _description = 'Stock Inventory Line'
    
    inventory_id = fields.Many2one('brandat.stock.inventory', string='الجرد', ondelete='cascade', required=True)
    product_id = fields.Many2one('brandat.product', string='المنتج', required=True)
    size_id = fields.Many2one('brandat.size', string='المقاس', required=True)
    color_id = fields.Many2one('brandat.color', string='اللون', required=True)
    
    theoretical_qty = fields.Integer(string='الكمية النظرية', readonly=True)
    real_qty = fields.Integer(string='الكمية الفعلية', required=True)
    difference = fields.Integer(string='الفرق', compute='_compute_difference', store=True)
    
    @api.depends('theoretical_qty', 'real_qty')
    def _compute_difference(self):
        for line in self:
            line.difference = line.real_qty - line.theoretical_qty


class BrandatStockAlert(models.Model):
    _name = 'brandat.stock.alert'
    _description = 'Stock Alert Configuration'
    
    product_id = fields.Many2one('brandat.product', string='المنتج', required=True)
    store_id = fields.Many2one('brandat.store', string='الفرع', required=True)
    min_quantity = fields.Integer(string='الحد الأدنى', required=True, default=10)
    active = fields.Boolean(string='نشط', default=True)
    
    _sql_constraints = [
        ('product_store_unique', 'unique(product_id, store_id)', 
         'يوجد تنبيه بالفعل لهذا المنتج في هذا الفرع!')
    ]
    
    @api.model
    def _check_stock_alerts(self):
        """دالة تشغل تلقائياً للتحقق من المخزون"""
        alerts = self.search([('active', '=', True)])
        
        for alert in alerts:
            stocks = self.env['brandat.stock'].search([
                ('product_id', '=', alert.product_id.id),
                ('store_id', '=', alert.store_id.id),
            ])
            
            total_qty = sum(stocks.mapped('quantity'))
            
            if total_qty < alert.min_quantity:
                # إرسال إشعار
                message = f"""
                    <p><strong>تنبيه نقص مخزون</strong></p>
                    <ul>
                        <li>المنتج: {alert.product_id.name}</li>
                        <li>الفرع: {alert.store_id.name}</li>
                        <li>الكمية الحالية: {total_qty}</li>
                        <li>الحد الأدنى: {alert.min_quantity}</li>
                    </ul>
                """
                
                self.env['mail.message'].create({
                    'message_type': 'notification',
                    'body': message,
                    'subject': f'تنبيه: نقص مخزون {alert.product_id.name}',
                })


# إضافة حقول جديدة لموديل المخزون
class BrandatStock(models.Model):
    _inherit = 'brandat.stock'
    
    min_quantity = fields.Integer(string='الحد الأدنى', default=10)
    state = fields.Selection([
        ('available', 'متاح'),
        ('low', 'منخفض'),
        ('out', 'نفذ')
    ], string='الحالة', compute='_compute_state', store=True)
    
    @api.depends('quantity', 'min_quantity')
    def _compute_state(self):
        for stock in self:
            if stock.quantity <= 0:
                stock.state = 'out'
            elif stock.quantity <= stock.min_quantity:
                stock.state = 'low'
            else:
                stock.state = 'available'