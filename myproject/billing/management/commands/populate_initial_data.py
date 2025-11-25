# billing/management/commands/populate_initial_data.py
"""
Script que permite poblar datos iniciales para facturación electrónica.
Uso:
- activar el entorno virtual en la terminal
- ejecutar el siguiente comando dentro de la ruta myproject

python manage.py populate_initial_data

"""
from django.core.management.base import BaseCommand
from billing.models import Product, Tax, ContractTemplate, Company, Partner, SunatCatalog, Journal, Sequence, InvoiceSerie
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Poblar datos iniciales para facturación electrónica'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Iniciando población de datos...')
        
        if not Company.objects.exists():
            self.stdout.write(self.style.ERROR('❌ No hay compañías configuradas. Por favor, crea al menos una compañía antes de ejecutar este comando.'))
            return
        
        # Crear productos
        self.create_products()
        
        # Crear impuestos
        self.create_taxes()
        
        # Crear plantillas de contrato
        self.create_contract_templates()
        
        # V2 segunda migración
        # Población de catálogos SUNAT si es necesario
        self.populate_sunat_catalogs()  
        # Población de diarios y secuencias
        self.populate_journals_and_sequences()
        # Población de series de facturación
        self.populate_invoice_series()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Datos poblados exitosamente!')
        )

    def populate_journals_and_sequences(self):
        """Crear diarios y secuencias iniciales para TODAS las compañías"""
        companies = Company.objects.all()
        
        if not companies:
            self.stdout.write(self.style.WARNING('No hay compañías configuradas'))
            return
        
        for company in companies:
            self.stdout.write(f"📝 Configurando diarios y secuencias para: {company}")
            
            # Crear secuencia para FACTURAS
            sequence_factura, created = Sequence.objects.get_or_create(
                code=f'sale.invoice.{company.id}',
                company=company,
                defaults={
                    'name': f'Secuencia Facturas de Venta - {company}',
                    'prefix': 'F001-',
                    'number_next': 1,
                    'padding': 8
                }
            )
            
            # Crear secuencia para BOLETAS
            sequence_boleta, created = Sequence.objects.get_or_create(
                code=f'sale.ticket.{company.id}',
                company=company,
                defaults={
                    'name': f'Secuencia Boletas de Venta - {company}',
                    'prefix': 'B001-',
                    'number_next': 1,
                    'padding': 8
                }
            )
            
            # Crear diario de ventas para FACTURAS
            journal_factura, created = Journal.objects.get_or_create(
                code=f'INV{company.id}',
                company=company,
                defaults={
                    'name': f'Facturas de Venta - {company}',
                    'type': 'sale',
                    'sequence': sequence_factura.code
                }
            )
            
            # Crear diario de ventas para BOLETAS
            journal_boleta, created = Journal.objects.get_or_create(
                code=f'TKT{company.id}',
                company=company,
                defaults={
                    'name': f'Boletas de Venta - {company}',
                    'type': 'sale',
                    'sequence': sequence_boleta.code
                }
            )
            
            if created:
                self.stdout.write(f"    ✅ Diarios y secuencias creados para: {company} - {journal_factura.code}, {journal_boleta.code}")
            else:
                self.stdout.write(f"    ⚠️ Diarios y secuencias ya existe: {company} - {journal_factura.code}, {journal_boleta.code}")

    def populate_invoice_series(self):
        """Crear series de facturación para TODAS las compañías"""
        companies = Company.objects.all()
        
        for company in companies:
            self.stdout.write(f"📋 Creando series para: {company}")
            
            # Obtener diarios y secuencias de esta compañía
            journal_factura = Journal.objects.filter(
                company=company, 
                code=f'INV{company.id}'
            ).first()
            
            journal_boleta = Journal.objects.filter(
                company=company, 
                code=f'TKT{company.id}'
            ).first()
            
            sequence_factura = Sequence.objects.filter(
                company=company, 
                code=f'sale.invoice.{company.id}'
            ).first()
            
            sequence_boleta = Sequence.objects.filter(
                company=company, 
                code=f'sale.ticket.{company.id}'
            ).first()
            
            # Crear serie de FACTURA
            if journal_factura and sequence_factura:
                serie_factura, created = InvoiceSerie.objects.get_or_create(
                    series='F001',
                    company=company,
                    defaults={
                        'name': f'Serie Factura Electrónica - {company}',
                        'journal': journal_factura,
                        'sequence': sequence_factura,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f"    ✅ Serie Factura creada: {serie_factura.name}")
                else:
                    self.stdout.write(f"    ⚠️ Serie Factura ya existe: {serie_factura.name}")
            
            # Crear serie de BOLETA
            if journal_boleta and sequence_boleta:
                serie_boleta, created = InvoiceSerie.objects.get_or_create(
                    series='B001',
                    company=company,
                    defaults={
                        'name': f'Serie Boleta Electrónica - {company}',
                        'journal': journal_boleta,
                        'sequence': sequence_boleta,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f"    ✅ Serie Boleta creada: {serie_boleta.name}")
                else:
                    self.stdout.write(f"    ⚠️ Serie Boleta ya existe: {serie_boleta.name}")
    
    def populate_sunat_catalogs(self):
        """Poblar catálogos SUNAT esenciales"""
        self.stdout.write(f"📚 Población de catálogos SUNAT...")
        catalogs = [
            # Catálogo 01 - Tipos de Documento
            {'code': '01', 'name': 'FACTURA', 'catalog_type': '01'},
            {'code': '03', 'name': 'BOLETA DE VENTA', 'catalog_type': '01'},
            {'code': '07', 'name': 'NOTA DE CRÉDITO', 'catalog_type': '01'},
            {'code': '08', 'name': 'NOTA DE DÉBITO', 'catalog_type': '01'},
            
            # Catálogo 51 - Tipos de Operación
            {'code': '0101', 'name': 'Venta interna', 'catalog_type': '51'},
            {'code': '0102', 'name': 'Exportación', 'catalog_type': '51'},
            {'code': '0103', 'name': 'No Domiciliados', 'catalog_type': '51'},
            {'code': '0104', 'name': 'Venta Interna - Anticipo', 'catalog_type': '51'},
            
            # Catálogo 10 - Afectación IGV
            {'code': '10', 'name': 'Gravado - Operación Onerosa', 'catalog_type': '10'},
            {'code': '11', 'name': 'Gravado - Retiro por premio', 'catalog_type': '10'},
            {'code': '12', 'name': 'Gravado - Retiro por donación', 'catalog_type': '10'},
            {'code': '13', 'name': 'Gravado - Retiro', 'catalog_type': '10'},
            {'code': '14', 'name': 'Gravado - Retiro por publicidad', 'catalog_type': '10'},
            {'code': '15', 'name': 'Gravado - Bonificaciones', 'catalog_type': '10'},
            {'code': '16', 'name': 'Gravado - Retiro por entrega a trabajadores', 'catalog_type': '10'},
            {'code': '17', 'name': 'Gravado - IVAP', 'catalog_type': '10'},
            {'code': '20', 'name': 'Exonerado - Operación Onerosa', 'catalog_type': '10'},
            {'code': '21', 'name': 'Exonerado - Transferencia Gratuita', 'catalog_type': '10'},
            {'code': '30', 'name': 'Inafecto - Operación Onerosa', 'catalog_type': '10'},
            {'code': '31', 'name': 'Inafecto - Retiro por Bonificación', 'catalog_type': '10'},
            {'code': '32', 'name': 'Inafecto - Retiro', 'catalog_type': '10'},
            {'code': '33', 'name': 'Inafecto - Retiro por Muestras Médicas', 'catalog_type': '10'},
            {'code': '34', 'name': 'Inafecto - Retiro por Convenio Colectivo', 'catalog_type': '10'},
            {'code': '35', 'name': 'Inafecto - Retiro por premio', 'catalog_type': '10'},
            {'code': '36', 'name': 'Inafecto - Retiro por publicidad', 'catalog_type': '10'},
            {'code': '37', 'name': 'Inafecto - Transferencia Gratuita', 'catalog_type': '10'},
            {'code': '40', 'name': 'Exportación', 'catalog_type': '10'},
            
            # Tipos de Tributo
            {'code': '1000', 'name': 'IGV', 'catalog_type': 'tribute'},
            {'code': '1016', 'name': 'IVAP', 'catalog_type': 'tribute'},
            {'code': '2000', 'name': 'ISC', 'catalog_type': 'tribute'},
            {'code': '7152', 'name': 'ICBPER', 'catalog_type': 'tribute'},
            
            # Tipos de Nota
            {'code': '01', 'name': 'Anulación de la operación', 'catalog_type': 'note_type'},
            {'code': '02', 'name': 'Anulación por error en el RUC', 'catalog_type': 'note_type'},
            {'code': '03', 'name': 'Corrección por error en la descripción', 'catalog_type': 'note_type'},
            {'code': '04', 'name': 'Descuento global', 'catalog_type': 'note_type'},
            {'code': '05', 'name': 'Descuento por ítem', 'catalog_type': 'note_type'},
            {'code': '06', 'name': 'Devolución total', 'catalog_type': 'note_type'},
            {'code': '07', 'name': 'Devolución por ítem', 'catalog_type': 'note_type'},
            {'code': '08', 'name': 'Bonificación', 'catalog_type': 'note_type'},
            {'code': '09', 'name': 'Disminución en el valor', 'catalog_type': 'note_type'},
            {'code': '10', 'name': 'Otros conceptos', 'catalog_type': 'note_type'},
            {'code': '11', 'name': 'Ajustes de operaciones de exportación', 'catalog_type': 'note_type'},
            {'code': '12', 'name': 'Ajustes afectos al IVAP', 'catalog_type': 'note_type'},
        ]
        
        for catalog_data in catalogs:
            catalog, created = SunatCatalog.objects.get_or_create(
                code=catalog_data['code'],
                catalog_type=catalog_data['catalog_type'],
                defaults=catalog_data
            )
            if created:
                self.stdout.write(f"    ✅ Catálogo creado: {catalog} ")
            else:
                self.stdout.write(f"    ⚠️ Catálogo ya existe: {catalog}")
                    
    def create_products(self):
        self.stdout.write(f"⏹️ Creando Productos Iniciales...")
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
                self.stdout.write(f"    ✅ Producto creado: {product.name}")
            else:
                self.stdout.write(f"    ⚠️ Producto ya existe: {product.name}")

    def create_taxes(self):
        companies = Company.objects.all()
        
        for company in companies:
            self.stdout.write(f"💰 Creando impuestos para: {company}")
            
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
            
            taxes_data = [
                {
                    'name': 'IGV 18%',
                    'type_tax_use': 'sale',
                    'amount_type': 'percent',
                    'amount': 18.0,
                    'company': company,
                    'sequence': f'tax_igv_{company.id}',
                    'description': 'Impuesto General a las Ventas 18%',
                    'price_include': False,
                    'include_base_amount': False,
                    'code_fe': '1000',
                    'affectation_type': affectation_igv,
                    'is_icbper': False
                },
                {
                    'name': 'Exportación 0%',
                    'type_tax_use': 'sale', 
                    'amount_type': 'percent',
                    'amount': 0.0,
                    'company': company,
                    'sequence': f'tax_exp_{company.id}',
                    'description': 'Exportación 0%',
                    'price_include': False,
                    'include_base_amount': False,
                    'code_fe': '1000',
                    'affectation_type': affectation_igv,
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
                    self.stdout.write(f"    ✅ Impuesto creado: {tax.name} para {company}")
                else:
                    self.stdout.write(f"    ⚠️ Impuesto ya existe: {tax.name} para {company}")

    def create_contract_templates(self):
        companies = Company.objects.all()
        admin_user = User.objects.filter(is_superuser=True).first()
        
        template_configs = [
            {'code': '15D', 'name': 'Contrato 15 Días', 'interval': 15, 'rule_type': 'daily'},
            {'code': '1M', 'name': 'Plazo Forzoso 1 Mes', 'interval': 1, 'rule_type': 'monthly'},
            {'code': '2M', 'name': 'Plazo Forzoso 2 Meses', 'interval': 2, 'rule_type': 'monthly'},
            {'code': '3M', 'name': 'Plazo Forzoso 3 Meses', 'interval': 3, 'rule_type': 'monthly'},
            {'code': '6M', 'name': 'Plazo Forzoso 6 Meses', 'interval': 6, 'rule_type': 'monthly'},
            {'code': '1A', 'name': 'Plazo Forzoso 1 Año', 'interval': 1, 'rule_type': 'yearly'},
        ]
        
        for company in companies:
            self.stdout.write(f"📄 Creando plantillas para: {company}")
            
            for config in template_configs:
                template_data = {
                    'name': f"{config['name']} - {company}",
                    'code': f"{config['code']}",
                    'description': f"{config['name']} - Compañía {company}",
                    'recurring_rule_type': config['rule_type'],
                    'recurring_interval': config['interval'],
                    'recurring_rule_boundary': 'limited',
                    'recurring_rule_count': 1,
                    'payment_mode': 'draft_invoice',
                    'auto_close_limit': 15,
                    'user_closable': True,
                    'calculate_upsell': True,
                    'is_massive': False,
                    'company': company,
                    'created_by': admin_user,
                    'updated_by': admin_user
                }
                
                template, created = ContractTemplate.objects.get_or_create(
                    code=template_data['code'],
                    company=template_data['company'],
                    defaults=template_data
                )
                if created:
                    self.stdout.write(f"    ✅ Plantilla creada: {template.name}")
                else:
                    self.stdout.write(f"    ⚠️ Plantilla ya existe: {template.name}")
                
                