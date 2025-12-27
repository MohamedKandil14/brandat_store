# -*- coding: utf-8 -*-
{
    'name': 'براندات - إدارة المنتجات والمبيعات',
    'version': '1.0',
    'summary': 'نظام متكامل لإدارة المنتجات والمخزون والمبيعات',
    'sequence': 10,
    'description': """
        نظام براندات الشامل
        ===================
        * لوحة تحكم احترافية
        * إدارة الفروع
        * إدارة المنتجات (مقاسات - ألوان)
        * إدارة المخزون المتقدمة
        * تحويل البضاعة بين الفروع
        * جرد المخزون
        * تنبيهات نقص المخزون
        * إدارة المبيعات والفواتير
        * المرتجعات والاستبدال
        * طباعة فواتير احترافية
        * إرسال الفواتير بالإيميل والواتساب
        * إدارة العملاء ونقاط الولاء
        * إدارة الموردين وفواتير الشراء
        * إدارة الموظفين والحضور
        * عمولات الموظفين
        * تقارير مفصلة
    """,
    'category': 'Sales/Inventory',
    'author': 'Your Name',
    'website': 'https://example.com',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/dashboard_data.xml',
        'views/menu.xml',
        'views/dashboard_view.xml',
        'views/store_view.xml',
        'views/size_view.xml',
        'views/color_view.xml',
        'views/product_view.xml',
        'views/stock_view.xml',
        'views/stock_advanced_view.xml',
        'views/partner_view.xml',
        'views/employee_view.xml',
        'views/sale_view.xml',
        'views/sale_return_view.xml',
        'views/treasury_view.xml',         
        'views/transaction_view.xml',      
        'views/payment_view.xml',          
        'views/expense_view.xml',          
        'views/account_report_view.xml',
        'views/company_settings_view.xml',
        'views/report_view.xml',
        'reports/sale_report.xml',
        'reports/email_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'brandat_product/static/src/css/brandat_fashion_theme.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}