# billing/management/commands/populate_initial_data.py
"""
Script que permite poblar datos iniciales para facturación electrónica.
Uso:
- activar el entorno virtual en la terminal
- ejecutar el siguiente comando dentro de la ruta myproject

python manage.py populate_initial_data

"""
from django.core.management.base import BaseCommand
from billing.models import Product, Tax, ContractTemplate, Company, Partner, SunatCatalog
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Poblar datos iniciales para facturación electrónica'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Iniciando población de datos...')
        
        # Crear productos
        self.create_products()
        
        # Crear impuestos
        self.create_taxes()
        
        # Crear plantillas de contrato
        self.create_contract_templates()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Datos poblados exitosamente!')
        )

    def create_products(self):
        products_data = [
            {
                'defaultcode': 'S00140',
                'name': 'Internet FBC 80',
                'is_active': True,
                'onu_code': '51473',
                'product_type': 'service',
                'uom_code': 'NIU'
            },
            {
                'defaultcode': 'S00141', 
                'name': 'Internet FBC10',
                'is_active': True,
                'onu_code': '51473',
                'product_type': 'service', 
                'uom_code': 'NIU'
            },
            {
                'defaultcode': 'S00142',
                'name': 'Internet FBC100', 
                'is_active': True,
                'onu_code': '51473',
                'product_type': 'service',
                'uom_code': 'NIU'
            },
            {
                'defaultcode': 'S00143',
                'name': 'Internet FBC1000',
                'is_active': True, 
                'onu_code': '51473',
                'product_type': 'service',
                'uom_code': 'NIU'
            },
            {
                'defaultcode': 'CON_000074',
                'name': 'UNIFORME CORPORATIVO',
                'is_active': True,
                'onu_code': '24527', 
                'product_type': 'product',
                'uom_code': 'ZZ'
            }
        ]
        
        company = Company.objects.first()
        
        for product_data in products_data:
            product, created = Product.objects.get_or_create(
                defaultcode=product_data['defaultcode'],
                defaults={
                    'name': product_data['name'],
                    'is_active': product_data['is_active'],
                    'onu_code': product_data['onu_code'],
                    'product_type': product_data['product_type'],
                    'uom_code': product_data['uom_code']
                }
            )
            if created:
                self.stdout.write(f"✅ Producto creado: {product.name}")
            else:
                self.stdout.write(f"⚠️ Producto ya existe: {product.name}")

    def create_taxes(self):
        company = Company.objects.first()
        
        # Crear catálogo de afectación IGV si no existe
        affectation_igv, _ = SunatCatalog.objects.get_or_create(
            catalog_type='10',
            code='10',
            defaults={
                'name': 'Gravado - Operación Onerosa',
                'pse_code': '10',
                'is_active': True
            }
        )
        
        affectation_detraction, _ = SunatCatalog.objects.get_or_create(
            catalog_type='10', 
            code='20',
            defaults={
                'name': 'Exonerado - Operación Onerosa',
                'pse_code': '20',
                'is_active': True
            }
        )
        
        taxes_data = [
            {
                'name': 'IGV 18%',
                'type_tax_use': 'sale',
                'amount_type': 'percent',
                'amount': 18.0,
                'company': company,
                'sequence': 'tax_igv_001',
                'description': 'Impuesto General a las Ventas 18%',
                'price_include': False,
                'include_base_amount': False,
                'code_fe': '1000',
                'affectation_type': affectation_igv,
                'is_icbper': False
            },
            {
                'name': 'Detracción 12%',
                'type_tax_use': 'sale', 
                'amount_type': 'percent',
                'amount': 12.0,
                'company': company,
                'sequence': 'tax_det_001',
                'description': 'Detracción 12%',
                'price_include': False,
                'include_base_amount': False,
                'code_fe': '2000',
                'affectation_type': affectation_detraction,
                'is_icbper': False
            }
        ]
        
        for tax_data in taxes_data:
            tax, created = Tax.objects.get_or_create(
                name=tax_data['name'],
                company=tax_data['company'],
                defaults=tax_data
            )
            if created:
                self.stdout.write(f"✅ Impuesto creado: {tax.name}")
            else:
                self.stdout.write(f"⚠️ Impuesto ya existe: {tax.name}")

    def create_contract_templates(self):
        try:
            partner_2 = Partner.objects.get(id=2)
            partner_3 = Partner.objects.get(id=3)
            
            company_2 = Company.objects.filter(partner=partner_2).first()
            company_3 = Company.objects.filter(partner=partner_3).first()
        except (Partner.DoesNotExist, AttributeError):
            self.stdout.write("⚠️ Partners 2 y/o 3 no existen. Usando compañías por defecto.")
            company_2 = Company.objects.first()
            company_3 = Company.objects.last() if Company.objects.count() > 1 else Company.objects.first()
        
        admin_user = User.objects.filter(is_superuser=True).first()
        
        templates_data = [
            # ... (los mismos datos de plantillas que en el script anterior)
            {
                'name': 'Contrato 15 Días - Servicio Rápido',
                'code': '15D',
                'description': 'Contrato de servicio por 15 días',
                'recurring_rule_type': 'daily',
                'recurring_interval': 15,
                'recurring_rule_boundary': 'limited',
                'recurring_rule_count': 1,
                'payment_mode': 'draft_invoice',
                'auto_close_limit': 3,
                'user_closable': True,
                'calculate_upsell': True,
                'is_massive': False,
                'company': company_2,
                'created_by': admin_user,
                'updated_by': admin_user
            },
        # 1 Mes
        {
            'name': 'Plazo Forzoso 1 Mes S/Corte',
            'code': '1M',
            'description': 'Contrato mensual renovable',
            'recurring_rule_type': 'monthly',
            'recurring_interval': 1,
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 1,
            'payment_mode': 'draft_invoice',
            'auto_close_limit': 15,
            'user_closable': True,
            'calculate_upsell': True,
            'is_massive': True,
            'company': company_2,
            'created_by': admin_user,
            'updated_by': admin_user
        },
        # 2 Meses
        {
            'name': 'Plazo Forzoso 2 Meses S/Corte',
            'code': '2M',
            'description': 'Contrato bimestral',
            'recurring_rule_type': 'monthly',
            'recurring_interval': 2,
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 1,
            'payment_mode': 'draft_invoice',
            'auto_close_limit': 15,
            'user_closable': True,
            'calculate_upsell': True,
            'is_massive': False,
            'company': company_3,
            'created_by': admin_user,
            'updated_by': admin_user
        },
        # 3 Meses
        {
            'name': 'Plazo Forzoso 3 Meses S/Corte',
            'code': '3M',
            'description': 'Contrato trimestral',
            'recurring_rule_type': 'monthly',
            'recurring_interval': 3,
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 1,
            'payment_mode': 'draft_invoice',
            'auto_close_limit': 15,
            'user_closable': True,
            'calculate_upsell': True,
            'is_massive': True,
            'company': company_2,
            'created_by': admin_user,
            'updated_by': admin_user
        },
        # 4 Meses
        {
            'name': 'Plazo Forzoso 4 Meses S/Corte',
            'code': '4M',
            'description': 'Contrato cuatrimestral',
            'recurring_rule_type': 'monthly',
            'recurring_interval': 4,
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 1,
            'payment_mode': 'manual',
            'auto_close_limit': 15,
            'user_closable': False,
            'calculate_upsell': True,
            'is_massive': False,
            'company': company_3,
            'created_by': admin_user,
            'updated_by': admin_user
        },
        # 6 Meses
        {
            'name': 'Plazo Forzoso 6 Meses C/Corte',
            'code': '6M',
            'description': 'Contrato semestral con corte',
            'recurring_rule_type': 'monthly',
            'recurring_interval': 6,
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 1,
            'payment_mode': 'draft_invoice',
            'auto_close_limit': 15,
            'user_closable': True,
            'calculate_upsell': True,
            'is_massive': True,
            'company': company_2,
            'created_by': admin_user,
            'updated_by': admin_user
        },
        # 1 Año
        {
            'name': 'Plazo Forzoso 1 Año S/Corte',
            'code': '1A',
            'description': 'Contrato anual renovable',
            'recurring_rule_type': 'yearly',
            'recurring_interval': 1,
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 1,
            'payment_mode': 'validate_invoice',
            'auto_close_limit': 30,
            'user_closable': True,
            'calculate_upsell': True,
            'is_massive': False,
            'company': company_3,
            'created_by': admin_user,
            'updated_by': admin_user
        }
            # ... (agrega las demás plantillas aquí)
        ]
        
        for template_data in templates_data:
            template, created = ContractTemplate.objects.get_or_create(
                code=template_data['code'],
                company=template_data['company'],
                defaults=template_data
            )
            if created:
                self.stdout.write(f"✅ Plantilla creada: {template.name}")
            else:
                self.stdout.write(f"⚠️ Plantilla ya existe: {template.name}")