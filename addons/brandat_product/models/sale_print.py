from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64

class BrandatSale(models.Model):
    _inherit = 'brandat.sale'
    
    # حذف الحقول اللي بتعتمد على company_id
    # وخلّيها تجيب البيانات من الإعدادات مباشرة
    
    def action_print_invoice(self):
        """طباعة الفاتورة"""
        self.ensure_one()
        return self.env.ref('brandat_product.action_report_brandat_sale').report_action(self)
    
    def action_send_email(self):
        """إرسال الفاتورة بالإيميل"""
        self.ensure_one()
        
        if not self.customer_id and not self.partner_id:
            raise ValidationError('يجب تحديد عميل أولاً!')
        
        email = None
        if self.customer_id and self.customer_id.email:
            email = self.customer_id.email
        elif self.partner_id and self.partner_id.email:
            email = self.partner_id.email
        
        if not email:
            raise ValidationError('لا يوجد بريد إلكتروني للعميل!')
        
        # إنشاء PDF
        pdf_content = self.env.ref('brandat_product.action_report_brandat_sale')._render_qweb_pdf(self.ids)
        pdf_base64 = base64.b64encode(pdf_content[0])
        
        # إنشاء مرفق
        attachment = self.env['ir.attachment'].create({
            'name': f'فاتورة_{self.name}.pdf',
            'type': 'binary',
            'datas': pdf_base64,
            'res_model': 'brandat.sale',
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        
        # إرسال الإيميل
        template = self.env.ref('brandat_product.email_template_brandat_sale')
        template.attachment_ids = [(6, 0, [attachment.id])]
        template.send_mail(self.id, force_send=True)
        
        self.message_post(
            body=f'تم إرسال الفاتورة بالبريد الإلكتروني إلى {email}',
            subject='إرسال الفاتورة'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'تم الإرسال',
                'message': f'تم إرسال الفاتورة إلى {email}',
                'type': 'success',
            }
        }
    
    def action_send_whatsapp(self):
        """إرسال الفاتورة عبر واتساب"""
        self.ensure_one()
        
        if not self.customer_id and not self.partner_id:
            raise ValidationError('يجب تحديد عميل أولاً!')
        
        mobile = None
        customer_name = 'العميل'
        
        if self.customer_id:
            mobile = self.customer_id.mobile
            customer_name = self.customer_id.name
        elif self.partner_id:
            mobile = self.partner_id.mobile or self.partner_id.phone
            customer_name = self.partner_id.name
        
        if not mobile:
            raise ValidationError('لا يوجد رقم موبايل للعميل!')
        
        # الحصول على إعدادات الشركة
        settings = self.env['brandat.company.settings'].get_settings()
        
        # تنسيق الرسالة
        message = f"""
*{settings.company_name}*
{'='*30}

*فاتورة رقم: {self.name}*

📋 *تفاصيل الفاتورة:*
العميل: {customer_name}
التاريخ: {self.date.strftime('%Y-%m-%d')}
الفرع: {self.store_id.name}

🛍️ *المنتجات:*
"""
        for line in self.line_ids:
            message += f"• {line.product_id.name}\n"
            message += f"  {line.size_id.name} - {line.color_id.name}\n"
            message += f"  الكمية: {line.quantity} × {line.price_unit:.2f} = {line.price_subtotal:.2f} جنيه\n\n"
        
        message += f"💰 *الملخص المالي:*\n"
        message += f"المبلغ قبل الخصم: {self.amount_untaxed:.2f} جنيه\n"
        
        if self.discount_amount > 0:
            message += f"الخصم: {self.discount_amount:.2f} جنيه\n"
        
        message += f"*الإجمالي النهائي: {self.amount_total:.2f} جنيه*\n\n"
        
        if self.customer_id and self.loyalty_points_earned > 0:
            message += f"🎁 نقاط الولاء المكتسبة: {self.loyalty_points_earned:.2f} نقطة\n\n"
        
        message += f"📞 للاستفسار: {settings.phone1}\n"
        message += f"شكراً لتعاملكم معنا 🙏"
        
        # إنشاء رابط واتساب
        phone = mobile.replace('+', '').replace(' ', '').replace('-', '')
        
        # URL encoding للرسالة
        import urllib.parse
        encoded_message = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/{phone}?text={encoded_message}"
        
        self.message_post(
            body=f'تم إرسال الفاتورة عبر واتساب إلى {mobile}',
            subject='إرسال عبر واتساب'
        )
        
        return {
            'type': 'ir.actions.act_url',
            'url': whatsapp_url,
            'target': 'new',
        }


class BrandatCompanySettings(models.Model):
    _name = 'brandat.company.settings'
    _description = 'Company Settings'
    
    name = fields.Char(string='اسم الإعدادات', default='إعدادات الشركة', required=True)
    company_name = fields.Char(string='اسم الشركة', required=True, default='براندات للملابس')
    company_name_en = fields.Char(string='اسم الشركة (English)', default='Brandat Clothing')
    company_logo = fields.Binary(string='شعار الشركة')
    company_stamp = fields.Binary(string='ختم الشركة')
    
    phone1 = fields.Char(string='هاتف 1', required=True, default='+20 123 456 7890')
    phone2 = fields.Char(string='هاتف 2')
    email = fields.Char(string='البريد الإلكتروني', required=True, default='info@brandat.com')
    website = fields.Char(string='الموقع الإلكتروني')
    
    address_ar = fields.Text(string='العنوان (عربي)', required=True, default='القاهرة، مصر')
    address_en = fields.Text(string='العنوان (English)')
    
    tax_number = fields.Char(string='الرقم الضريبي')
    commercial_registration = fields.Char(string='السجل التجاري')
    
    invoice_footer = fields.Text(string='تذييل الفاتورة', 
        default='شكراً لثقتكم - Thanks for your trust')
    terms_and_conditions = fields.Text(string='الشروط والأحكام',
        default='• البضاعة المباعة لا ترد ولا تستبدل إلا بعذر\n• يرجى فحص البضاعة قبل المغادرة\n• شكراً لثقتكم')
    
    show_stamp = fields.Boolean(string='إظهار الختم', default=True)
    show_signature = fields.Boolean(string='إظهار التوقيع', default=True)
    
    _sql_constraints = [
        ('unique_settings', 'unique(name)', 'يمكن إنشاء إعدادات واحدة فقط!')
    ]
    
    @api.model
    def get_settings(self):
        """الحصول على إعدادات الشركة"""
        settings = self.search([], limit=1)
        if not settings:
            settings = self.create({
                'name': 'إعدادات الشركة',
                'company_name': 'براندات للملابس',
                'phone1': '+20 123 456 7890',
                'email': 'info@brandat.com',
                'address_ar': 'القاهرة، مصر',
            })
        return settings