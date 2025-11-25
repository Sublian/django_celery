# billing/models.py
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from dateutil.relativedelta import relativedelta

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

# === MODELOS EXISTENTES (MANTENIDOS) ===
class Partner(TimeStampedModel):
    name = models.CharField(max_length=255, verbose_name="Nombre o Razón Social")
    display_name = models.CharField(max_length=255, verbose_name="Nombre para Mostrar")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    email_secondary = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico Secundario")
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('dni', 'DNI'),
            ('ruc', 'RUC'),
            ('ce', 'Carnet de Extranjería'),
            ('pasaporte', 'Pasaporte'),
            ('otro', 'Otro'),
        ],
        default="dni"
    )
    num_document = models.CharField(max_length=20, unique=False, blank=True, null=True, verbose_name="Número de Documento")
    ref = models.CharField(max_length=64, unique=True, blank=True, null=True, verbose_name="Referencia Interna")
    website = models.URLField(blank=True, null=True, verbose_name="Sitio Web")
    comment = models.TextField(blank=True, null=True, verbose_name="Notas Adicionales")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    is_foreign = models.BooleanField(default=False, verbose_name="Es Extranjero")
    is_employee = models.BooleanField(default=False, verbose_name="Es Empleado")
    is_supplier = models.BooleanField(default=False, verbose_name="Es Proveedor")
    is_customer = models.BooleanField(default=True, verbose_name="Es Cliente")
    is_company = models.BooleanField(default=False, verbose_name="Es Empresa")
    is_detractor = models.BooleanField(default=False, verbose_name="Sujeto a Detracción")
    is_partner_retention = models.BooleanField(default=False, verbose_name="Sujeto a Retención")
    street = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    street2 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección 2")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    mobile = models.CharField(max_length=20, blank=True, null=True, verbose_name="Móvil")
    ruc_state = models.CharField(max_length=3, blank=True, null=True, verbose_name="Estado RUC")
    ruc_condition = models.CharField(max_length=3, blank=True, null=True, verbose_name="Condición RUC")
    sunat_success = models.BooleanField(default=False, verbose_name="SUNAT Exitosa")
    sunat_state = models.CharField(max_length=3, blank=True, null=True, verbose_name="Estado SUNAT")
    sunat_condition = models.CharField(max_length=3, blank=True, null=True, verbose_name="Condición SUNAT")
    partner_latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Latitud")
    partner_longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Longitud")    
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Empresa Relacionada", related_name="children")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario Asociado", related_name='partner_profile')
    companies = models.ManyToManyField('Company', blank=True, related_name='partners', verbose_name="Compañías Asociadas")
    
    def __str__(self): 
        return self.name

class Company(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, verbose_name="Partner Asociado")
    sequence = models.CharField(max_length=64, verbose_name="Secuencia de Documentos")
    report_header = models.TextField(blank=True, null=True, verbose_name="Encabezado de Reportes")
    report_footer = models.TextField(blank=True, null=True, verbose_name="Pie de Página de Reportes")
    logo_web = models.ImageField(upload_to="company/logos/", blank=True, null=True, verbose_name="Logo para Web")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    active = models.BooleanField(default=True, verbose_name="Activo")
    tax_calculation_rounding_method = models.CharField(
        max_length=20, 
        choices=[('global','round_globally'), ('por linea','round_per_line')], 
        default='round_globally', 
        verbose_name="Método de Redondeo de Cálculo de Impuestos"
    )
    invoice_term = models.TextField(blank=True, null=True, verbose_name="Términos y Condiciones de la Factura")
    account_tax_periodicity = models.CharField(
        max_length=20, 
        choices=[
            ('monthly','Mensual'), 
            ('quarterly','Trimestral'), 
            ('biannual','Semestral'), 
            ('annual','Anual')
        ], 
        default='monthly', 
        verbose_name="Periodicidad de Declaración de Impuestos"
    )
    currency = models.ForeignKey('Currency', on_delete=models.PROTECT, null=True, blank=True, default=1, verbose_name="Moneda Predeterminada")
    account_tax_periodicity_reminder_day = models.IntegerField(default=7, verbose_name="Día de Recordatorio de Periodicidad de Impuestos")
    sunat_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto para SUNAT")
    currency_provider = models.CharField(max_length=50, blank=True, null=True, default='sunat', verbose_name="Proveedor de Moneda Extranjera")
    theme_color = models.CharField(max_length=20, default='light', verbose_name="Color del Tema")
    theme_text_color = models.CharField(max_length=20, default='dark', verbose_name="Color del Texto del Tema")
    text_color = models.CharField(max_length=20, default='black', verbose_name="Color del Texto")
    company_color = models.CharField(max_length=20, default='blue', verbose_name="Color de la Compañía")
    bank_comment = models.TextField(blank=True, null=True, verbose_name="Comentario Bancario")
    
    def __str__(self): 
        return self.partner.display_name or self.partner.name

class Currency(models.Model):
    name = models.CharField(max_length=3, unique=True, verbose_name="Código de Moneda")
    symbol = models.CharField(max_length=5, verbose_name="Símbolo de Moneda")
    decimal_places = models.IntegerField(default=2, verbose_name="Decimales de Redondeo")
    active = models.BooleanField(default=True, verbose_name="Activo")
    pse_code = models.CharField(max_length=3, verbose_name="Código PSE")
    singular_name = models.CharField(max_length=64, verbose_name="Nombre Singular")
    plural_name = models.CharField(max_length=64, verbose_name="Nombre Plural")
    fraction_name = models.CharField(max_length=64, verbose_name="Nombre de la Fracción")
    
    def __str__(self): 
        return self.name

class CurrencyRate(models.Model):
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name="Moneda")
    rate = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Tasa de Cambio")
    date_rate = models.DateField(default=timezone.now, verbose_name="Fecha de la Tasa")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, verbose_name="Compañía")
    purchase_rate = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Tasa de Compra", default=0)
    sale_rate = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Tasa de Venta", default=0)
    
    def __str__(self): 
        return f"{self.currency.name} - {self.rate} on {self.date_rate}"

class Product(models.Model):
    name = models.CharField(max_length=255)
    defaultcode = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    
    # === NUEVOS CAMPOS PARA FACTURACIÓN ELECTRÓNICA ===
    product_type = models.CharField(max_length=20, choices=[
        ('product', 'Producto'),
        ('service', 'Servicio')
    ], default='product')
    onu_code = models.CharField(max_length=10, blank=True, null=True)
    # is_advance = models.BooleanField(default=False)
    uom_code = models.CharField(max_length=5, default='NIU', choices=[
        ('NIU', 'Unidad'),
        ('ZZ', 'Servicio')
    ])
    
    def __str__(self): 
        return self.name

class Tax(models.Model):
    name = models.CharField(max_length=255)
    type_tax_use = models.CharField(max_length=50)
    amount_type = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    sequence = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Cambiado a Decimal
    description = models.TextField(blank=True, null=True)
    price_include = models.BooleanField(default=False)
    include_base_amount = models.BooleanField(default=False)
    code_fe = models.CharField(max_length=10, blank=True, null=True)
    
    # === NUEVOS CAMPOS PARA FACTURACIÓN ELECTRÓNICA ===
    affectation_type = models.ForeignKey(
        'SunatCatalog',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={'catalog_type': '10'},
        related_name='taxes'
    )
    is_icbper = models.BooleanField(default=False)
    eb_tributes_type = models.ForeignKey(
        'SunatCatalog',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={'catalog_type': 'tribute'},
        related_name='tribute_taxes'
    )
    
    def __str__(self): 
        return f"{self.name} ({self.amount}%)"

class Journal(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    code = models.CharField(max_length=10)
    type = models.CharField(max_length=50)
    sequence = models.CharField(max_length=64)
    voucher_edit = models.BooleanField(default=False)
    check_surrender = models.BooleanField(default=False)
    check_manual_sequencing = models.BooleanField(default=False)
    bank_position = models.CharField(max_length=50)
    is_factoring = models.BooleanField(default=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    refund_sequence = models.BooleanField(default=False)
    
    def __str__(self): 
        return f"{self.name} ({self.code})"

# === NUEVOS MODELOS PARA FACTURACIÓN ELECTRÓNICA ===

class SunatCatalog(models.Model):
    """Catálogos SUNAT (01, 51, 10, etc.)"""
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    catalog_type = models.CharField(max_length=20, choices=[
        ('01', 'Catálogo 01 - Tipo de Documento'),
        ('51', 'Catálogo 51 - Tipo de Operación'),
        ('10', 'Catálogo 10 - Tipo de Afectación IGV'),
        ('09', 'Catálogo 09 - Tipo de Guía'),
        ('tribute', 'Tipo de Tributo'),
        ('note_type', 'Tipo de Nota'),
        ('currency', 'Moneda'),
    ])
    pse_code = models.CharField(max_length=10, blank=True, null=True)
    code_sunat = models.CharField(max_length=10, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['catalog_type', 'code']
        indexes = [
            models.Index(fields=['catalog_type', 'code']),
        ]

    def __str__(self):
        return f"{self.catalog_type}-{self.code}: {self.name}"

class DetractionType(models.Model):
    """Tipos de detracción"""
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    pse_code = models.CharField(max_length=10)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.code}: {self.name}"

class PaymentMethod(models.Model):
    """Métodos de pago"""
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    pse_code = models.CharField(max_length=10)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.code}: {self.name}"

class AccountPaymentTerm(TimeStampedModel):
    """Términos de pago"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class AccountPaymentTermLine(TimeStampedModel):
    """Líneas de términos de pago"""
    payment_term = models.ForeignKey(AccountPaymentTerm, on_delete=models.CASCADE, related_name='lines')
    sequence = models.IntegerField(default=10)
    days = models.IntegerField(default=0, help_text="Días después de la fecha de emisión")
    day_of_the_month = models.IntegerField(
        null=True, 
        blank=True, 
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Día específico del mes"
    )
    option = models.CharField(max_length=30, choices=[
        ('day_after_invoice_date', 'Días después fecha factura'),
        ('after_invoice_month', 'Después del mes factura'),
        ('day_following_month', 'Día del mes siguiente'),
        ('day_current_month', 'Día del mes actual'),
    ], default='day_after_invoice_date')
    value = models.CharField(max_length=10, choices=[
        ('balance', 'Balance'),
        ('percent', 'Porcentaje'),
        ('fixed', 'Monto Fijo'),
    ], default='balance')
    value_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['sequence']
    
    def __str__(self):
        return f"{self.payment_term.name} - Línea {self.sequence}"

class InvoiceSerie(models.Model):
    """Series de facturación"""
    name = models.CharField(max_length=10)
    series = models.CharField(max_length=4)
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    manual = models.BooleanField(default=False)
    # === NUEVA RELACIÓN CON SECUENCIA ===
    sequence = models.ForeignKey(
        'Sequence',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoice_series',
        verbose_name="Secuencia Asociada"
    )
    
    def __str__(self):
        return f"{self.series} - {self.name}"
    
    def get_next_reference(self):
        """Obtiene la próxima referencia de la secuencia asociada"""
        if self.sequence:
            return self.sequence.next_by_code()
        return None

# === MODELOS PRINCIPALES DE FACTURACIÓN MEJORADOS ===

class SaleSubscription(TimeStampedModel):
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    date_start = models.DateField()
    date_end = models.DateField(null=True, blank=True)
    recurring_invoice_count = models.IntegerField(default=0)
    recurring_invoice_day = models.IntegerField(default=1)
    recurring_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    recurring_monthly = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, default="active")
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    uuid = models.CharField(max_length=64, unique=True)
    health = models.CharField(max_length=20, default="normal")
    to_renew = models.BooleanField(default=True)
    
    # === NUEVOS CAMPOS ===
    next_invoice_date = models.DateField(null=True, blank=True)
    invoicing_interval = models.CharField(max_length=20, choices=[
        ('daily', 'Diario'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
        ('quarterly', 'Trimestral'),
        ('yearly', 'Anual'),
    ], default='monthly')
    contract_template = models.ForeignKey(
        'ContractTemplate',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='subscriptions',
        verbose_name="Plantilla de Contrato"
    )
    # === CAMPOS DE SEGUIMIENTO ===
    invoices_generated = models.IntegerField(default=0, verbose_name="Facturas Generadas")
    total_invoiced = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Total Facturado")
    
    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['state']),
            models.Index(fields=['next_invoice_date']),
            models.Index(fields=['contract_template']),
        ]
    
    def __str__(self):
        return f"Sub #{self.id} - {self.partner.name}"
    
    def calculate_next_invoice_date(self):
        """Calcula la próxima fecha de facturación basada en la plantilla"""
        if self.contract_template and self.date_start:
            return self.contract_template.get_next_invoice_date(self.date_start)
        return None
    
    def save(self, *args, **kwargs):
        """Sobrescribir save para calcular automáticamente next_invoice_date"""
        if not self.next_invoice_date and self.contract_template:
            self.next_invoice_date = self.calculate_next_invoice_date()
        super().save(*args, **kwargs)

class SaleSubscriptionLine(TimeStampedModel):
    subscription = models.ForeignKey(SaleSubscription, related_name="lines", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_unit = models.DecimalField(max_digits=15, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_ids = models.ManyToManyField(Tax, blank=True)
    
    def __str__(self): 
        return f"SubLine {self.id} - {self.product.name}"

class AccountMove(TimeStampedModel):
    # === CAMPOS EXISTENTES ===
    invoice_number = models.CharField(max_length=64, unique=True, null=True, blank=True)
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    subscription = models.ForeignKey(SaleSubscription, on_delete=models.SET_NULL, null=True, blank=True)
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, default="draft")
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, default=1)
    currency_rate = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    type = models.CharField(max_length=20, 
                            choices=[
                                ('out_invoice', 'Factura de Cliente'),
                                ('out_refund', 'Nota de Crédito'),
                                ('in_invoice', 'Factura de Proveedor'),
                                ('in_refund', 'Nota de Débito de Proveedor'),
                            ], default='out_invoice')
    ref = models.CharField(max_length=200, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    file_name = models.CharField(max_length=200, null=True, blank=True)
    narration = models.TextField(blank=True, null=True)
    invoice_date = models.DateField(default=timezone.now)
    invoice_date_due = models.DateField(blank=True, null=True)
    hash_code = models.CharField(max_length=64, null=True, blank=True)
    print_version = models.IntegerField(default=1)
    billing_type = models.CharField(max_length=20,blank=True, null=True)
    sunat_state = models.CharField(max_length=3, choices=[
                                    ('0','Pendiente'), 
                                    ('1','Aceptado'), 
                                    ('2','Rechazado'), 
                                    ('3','Error de Envío'), 
                                    ('4', 'Pagado')
                                ], default='0')
    json_sent = models.JSONField(null=True, blank=True)
    json_response = models.JSONField(null=True, blank=True)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('dni', 'DNI'),
            ('ruc', 'RUC'),
            ('ce', 'Carnet de Extranjería'),
            ('pasaporte', 'Pasaporte'),
            ('otro', 'Otro'),
        ],
        default="dni"
    )
    serie = models.ForeignKey(
        InvoiceSerie, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True
    )
    op_type_sunat = models.ForeignKey(
        SunatCatalog, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True,
        limit_choices_to={'catalog_type': '51'},
        related_name='invoices_operation_type'
    )
    invoice_payment_term = models.ForeignKey(
        AccountPaymentTerm, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True
    )
    amount_tax = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    invoice_origin = models.CharField(max_length=128, null=True, blank=True)
    xml_version = models.FileField(upload_to="invoices/xml/", null=True, blank=True)
    qr_code = models.URLField(null=True, blank=True)
    
    # === NUEVOS CAMPOS PARA FACTURACIÓN ELECTRÓNICA ===
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    detraction_type = models.ForeignKey(DetractionType, on_delete=models.SET_NULL, null=True, blank=True)
    detraction_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    detraction_payment_method = models.ForeignKey(
        PaymentMethod, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='detraction_invoices'
    )
    retention_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_note_type = models.ForeignKey(
        SunatCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'catalog_type': 'note_type'},
        related_name='credit_notes'
    )
    debit_note_type = models.ForeignKey(
        SunatCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'catalog_type': 'note_type'},
        related_name='debit_notes'
    )
    
    # === URLs PERMANENTES S3 ===
    pdf_url_s3 = models.URLField(null=True, blank=True)
    xml_url_s3 = models.URLField(null=True, blank=True)
    cdr_url_s3 = models.URLField(null=True, blank=True)
    
    # === MOTIVO DE BAJA ===
    delete_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ref']),
            models.Index(fields=['invoice_date']),
            models.Index(fields=['state']),
            models.Index(fields=['sunat_state']),
        ]
    
    def __str__(self): 
        return f"Invoice #{self.invoice_number or self.id}"

class AccountMoveLine(TimeStampedModel):
    move = models.ForeignKey(AccountMove, related_name="lines", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_unit = models.DecimalField(max_digits=15, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax = models.ManyToManyField(Tax, blank=True)
    
    # === NUEVOS CAMPOS PARA FACTURACIÓN ELECTRÓNICA ===
    affectation_type = models.ForeignKey(
        SunatCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={'catalog_type': '10'},
        related_name='invoice_lines'
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igv_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    icbper_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # === TOTALES DE ALTA PRECISIÓN ===
    subtotal_origin = models.DecimalField(max_digits=18, decimal_places=10, default=0)
    igv_amount_origin = models.DecimalField(max_digits=18, decimal_places=10, default=0)
    total_origin = models.DecimalField(max_digits=18, decimal_places=10, default=0)
    
    # === ANTICIPOS ===
    is_advance_regularization = models.BooleanField(default=False)
    advance_invoice = models.ForeignKey(
        AccountMove,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advance_regularization_lines'
    )
    
    # === CÓDIGOS ESPECIALES ===
    sunat_product_code = models.CharField(max_length=10, blank=True, null=True)
    
    def __str__(self): 
        return f"InvLine {self.id} - {self.product.name}"

# === MODELOS ADICIONALES PARA FACTURACIÓN ELECTRÓNICA ===

class ElectronicInvoice(TimeStampedModel):
    """Información específica de facturación electrónica"""
    invoice = models.OneToOneField(AccountMove, on_delete=models.CASCADE, related_name='einvoice')
    
    # === TOTALES CALCULADOS ===
    total_gravada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_inafecta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_exonerada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gratuita = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_anticipo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_igv = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_icbper = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # === CÁLCULOS DE PRECISIÓN ===
    amount_total_origin = models.DecimalField(max_digits=18, decimal_places=10, default=0)
    
    # === JSON COMPLETO ===
    sent_json = models.JSONField(null=True, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    consult_json = models.JSONField(null=True, blank=True)
    
    # === CONFIGURACIONES ===
    save_changes = models.BooleanField(default=False)
    
    def __str__(self):
        return f"E-Invoice {self.invoice.ref}"

class RelatedDocument(TimeStampedModel):
    """Documentos relacionados para NC/ND"""
    invoice = models.ForeignKey(AccountMove, on_delete=models.CASCADE, related_name='related_documents')
    document_type = models.ForeignKey(
        SunatCatalog,
        on_delete=models.PROTECT,
        limit_choices_to={'catalog_type': '01'}
    )
    series = models.CharField(max_length=4)
    number = models.CharField(max_length=8)
    reference = models.CharField(max_length=20)
    
    class Meta:
        unique_together = ['invoice', 'reference']
    
    def __str__(self):
        return f"{self.reference}"

class GuideDocument(TimeStampedModel):
    """Guias de remisión relacionadas"""
    invoice = models.ForeignKey(AccountMove, on_delete=models.CASCADE, related_name='guide_documents')
    guide_number = models.CharField(max_length=20)
    guide_type = models.CharField(max_length=2, default='09')
    
    class Meta:
        unique_together = ['invoice', 'guide_number']
    
    def __str__(self):
        return f"Guía {self.guide_number}"

class ProviderConfig(TimeStampedModel):
    """Configuración de proveedores de facturación"""
    name = models.CharField(max_length=100)
    billing_type = models.CharField(max_length=1, choices=[
        ('0', 'Nubefact'),
        ('1', 'OdooFacturacion')
    ])
    api_url = models.URLField()
    api_token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    series = models.CharField(max_length=4)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    
    # Configuraciones específicas
    send_auto_sunat = models.BooleanField(default=True)
    send_auto_client = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['company', 'series', 'billing_type']
    
    def __str__(self):
        return f"{self.name} - {self.series}"

class SystemParameter(TimeStampedModel):
    """Parámetros generales del sistema"""
    key = models.CharField(max_length=100)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    
    # Parámetros específicos
    igv_tax = models.ForeignKey(Tax, on_delete=models.SET_NULL, null=True, blank=True)
    advance_products = models.ManyToManyField(Product, blank=True, related_name='advance_parameters')
    
    # Códigos de catálogo 51
    detraction_codes = models.ManyToManyField(
        SunatCatalog, 
        blank=True,
        related_name='detraction_parameters',
        limit_choices_to={'catalog_type': '51'}
    )
    advance_codes = models.ManyToManyField(
        SunatCatalog,
        blank=True,
        related_name='advance_parameters', 
        limit_choices_to={'catalog_type': '51'}
    )
    
    # Configuraciones de redondeo
    rounded_ebill = models.IntegerField(default=2)
    rounded_ebill_line = models.IntegerField(default=6)
    
    # Validaciones
    verify_amount_odoo = models.BooleanField(default=True)
    required_onu = models.BooleanField(default=False)
    comment_add_check = models.BooleanField(default=False)
    invoice_origin_check = models.BooleanField(default=False)
    
    # Configuraciones de envío
    bank_numbers = models.TextField(blank=True, null=True)
    send_address = models.CharField(max_length=30, choices=[
        ('street', 'Solo Dirección'),
        ('address_complete', 'Dirección Completa'),
        ('adress_complete_ubigeo', 'Dirección Completa con Ubigeo')
    ], default='street')
    send_multi_credits = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['company', 'key']
    
    def __str__(self):
        return f"{self.key} = {self.value}"
    

class ContractTemplate(TimeStampedModel):
    """Plantillas de contratos para definir tipos de contratos recurrentes"""
    active = models.BooleanField(default=True, verbose_name="Activo")
    name = models.CharField(max_length=255, verbose_name="Nombre del Contrato")
    code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    # === CONFIGURACIÓN DE RECURRENCIA ===
    recurring_rule_type = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Diario'),
            ('weekly', 'Semanal'),
            ('monthly', 'Mensual'),
            ('yearly', 'Anual'),
        ],
        default='monthly',
        verbose_name="Tipo de Recurrencia"
    )
    recurring_interval = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Intervalo de Recurrencia"
    )
    recurring_rule_boundary = models.CharField(
        max_length=20,
        choices=[
            ('unlimited', 'Ilimitado'),
            ('limited', 'Limitado'),
        ],
        default='unlimited',
        verbose_name="Límite de Recurrencia"
    )
    recurring_rule_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Número de Repeticiones"
    )
    
    # === CONFIGURACIÓN DE FACTURACIÓN ===
    payment_mode = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('draft_invoice', 'Borrador de Factura Automático'),
            ('validate_invoice', 'Factura Validada Automática'),
        ],
        default='manual',
        verbose_name="Modo de Facturación"
    )
    auto_close_limit = models.IntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        verbose_name="Límite de Cierre Automático (días)"
    )
    
    # === CONFIGURACIONES ADICIONALES ===
    user_closable = models.BooleanField(
        default=True,
        verbose_name="Usuario Puede Cerrar"
    )
    calculate_upsell = models.BooleanField(
        default=False,
        verbose_name="Calcular Upsell"
    )
    is_massive = models.BooleanField(
        default=False,
        verbose_name="Es Masivo"
    )
    
    # === RELACIONES ===
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía",
        related_name='contract_templates'
    )
    # invoice_mail_template = models.ForeignKey(
    #     'mail.MailTemplate',  # Asumiendo que existe un modelo de plantillas de email
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     verbose_name="Plantilla de Email para Factura"
    # )
    
    # === METADATOS ===
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_contract_templates',
        verbose_name="Creado Por"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_contract_templates',
        verbose_name="Actualizado Por"
    )
    
    class Meta:
        db_table = 'billing_contracttemplate'
        verbose_name = "Plantilla de Contrato"
        verbose_name_plural = "Plantillas de Contratos"
        indexes = [
            models.Index(fields=['active']),
            models.Index(fields=['code']),
            models.Index(fields=['is_massive']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name
    
    @property
    def duration_months(self):
        """Calcula la duración total en meses"""
        if self.recurring_rule_boundary == 'limited':
            return self.recurring_rule_count
        return None  # Ilimitado
    
    def get_next_invoice_date(self, last_invoice_date):
        """Calcula la próxima fecha de facturación basada en la última factura"""
        
        if self.recurring_rule_type == 'monthly':
            return last_invoice_date + relativedelta(months=self.recurring_interval)
        elif self.recurring_rule_type == 'yearly':
            return last_invoice_date + relativedelta(years=self.recurring_interval)
        elif self.recurring_rule_type == 'weekly':
            return last_invoice_date + relativedelta(weeks=self.recurring_interval)
        else:  # daily
            return last_invoice_date + relativedelta(days=self.recurring_interval)
    
# date: 2025-11-25
class Sequence(TimeStampedModel):
    """Secuencias para numeración de documentos (simplificado de ir_sequence)"""
    name = models.CharField(max_length=255, verbose_name="Nombre")
    code = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Código",
        help_text="Código único para identificar la secuencia"
    )
    implementation = models.CharField(
        max_length=20,
        choices=[
            ('standard', 'Standard'),
            ('no_gap', 'No Gap'),
        ],
        default='standard',
        verbose_name="Implementación"
    )
    active = models.BooleanField(default=True, verbose_name="Activa")
    prefix = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Prefijo",
        help_text="Ej: F001- para facturas"
    )
    suffix = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Sufijo"
    )
    number_next = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Próximo Número"
    )
    number_increment = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Incremento"
    )
    padding = models.IntegerField(
        default=8,
        validators=[MinValueValidator(1)],
        verbose_name="Relleno de ceros"
    )
    
    # === RELACIONES ===
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía",
        related_name='sequences'
    )
    
    class Meta:
        db_table = 'billing_sequence'
        verbose_name = "Secuencia"
        verbose_name_plural = "Secuencias"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['company', 'active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_next_number(self):
        """Obtiene el próximo número de la secuencia y lo incrementa"""
        if not self.active:
            raise ValueError(f"La secuencia {self.code} no está activa")
        
        next_number = self.number_next
        self.number_next += self.number_increment
        self.save(update_fields=['number_next', 'updated_at'])
        
        return next_number
    
    def format_number(self, number):
        """Formatea el número según el prefijo, sufijo y padding"""
        formatted_number = str(number).zfill(self.padding)
        
        result = ""
        if self.prefix:
            result += self.prefix
        result += formatted_number
        if self.suffix:
            result += self.suffix
            
        return result
    
    def next_by_code(self):
        """Obtiene el próximo número formateado (equivalente a next_by_code de Odoo)"""
        next_number = self.get_next_number()
        return self.format_number(next_number)

