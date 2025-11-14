# billing\models.py
from django.db import models
from django.utils import timezone
from django.conf import settings    # ← Importa la configuración global de Django


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Partner(TimeStampedModel):
    name = models.CharField(max_length=255, verbose_name="Nombre o Razón Social")
    display_name = models.CharField(max_length=255, verbose_name="Nombre para Mostrar")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    email_secondary = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico Secundario")
    document_type = models.CharField(
        max_length=20,
        choices=[
            ("dni", "DNI"),
            ("ruc", "RUC"),
            ("ce", "Carnet Extranjería"),
            ("passport", "Pasaporte"),
        ],
        default="dni"
    )
    num_document = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Número de Documento")
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
    parent= models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Empresa Relacionada", related_name="children")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario Asociado", related_name='partner_profile')
    companies = models.ManyToManyField('Company', blank=True, related_name='partners', verbose_name="Compañías Asociadas")
    def __str__(self): return self.name

# Company, Product, Tax...
class Currency(models.Model):
    name = models.CharField(max_length=3, unique=True, verbose_name="Código de Moneda")
    symbol = models.CharField(max_length=5, verbose_name="Símbolo de Moneda")
    decimal_places = models.IntegerField(default=2, verbose_name="Decimales de Redondeo")
    active = models.BooleanField(default=True, verbose_name="Activo")
    pse_code = models.CharField(max_length=3, verbose_name="Código PSE")
    singular_name = models.CharField(max_length=64, verbose_name="Nombre Singular")
    plural_name = models.CharField(max_length=64, verbose_name="Nombre Plural")
    fraction_name = models.CharField(max_length=64, verbose_name="Nombre de la Fracción")
    def __str__(self): return self.name

class CurrencyRate(models.Model):
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name="Moneda")
    rate = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Tasa de Cambio")
    date_rate = models.DateField(default=timezone.now, verbose_name="Fecha de la Tasa")
    company = models.ForeignKey('Company', on_delete=models.PROTECT, verbose_name="Compañía")
    purchase_rate = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Tasa de Compra", default=0)
    sale_rate = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Tasa de Venta", default=0)
    def __str__(self): return f"{self.currency.name} - {self.rate} on {self.date_rate}"
    
class Company(models.Model):
    name = models.CharField(max_length=255, verbose_name="Razón Social o Nombre Comercial")
    vat = models.CharField(max_length=11, unique=True, verbose_name="RUC")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, verbose_name="Partner Asociado")
    sequence = models.CharField(max_length=64, verbose_name="Secuencia de Documentos")
    report_header = models.TextField(blank=True, null=True, verbose_name="Encabezado de Reportes")
    report_footer = models.TextField(blank=True, null=True, verbose_name="Pie de Página de Reportes")
    logo_web = models.ImageField(upload_to="company/logos/", blank=True, null=True, verbose_name="Logo para Web")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    def __str__(self): return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    defaultcode = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Tax(models.Model):
    name = models.CharField(max_length=255)
    type_tax_use = models.CharField(max_length=50)
    amount_type = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    sequence = models.CharField(max_length=64)
    amount = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    price_include = models.BooleanField(default=False)
    include_base_amount = models.BooleanField(default=False)
    code_fe = models.CharField(max_length=10, blank=True, null=True)
    def __str__(self): return f"{self.name} ({self.rate}%)"

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
    def __str__(self): return f"{self.name} ({self.rate}%)"

# Suscripción
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
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    description = models.TextField(blank=True, null=True)
    uuid = models.CharField(max_length=64, unique=True)
    health = models.CharField(max_length=20, default="normal")
    to_renew = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Sub #{self.id} - {self.partner.name}"

class SaleSubscriptionLine(TimeStampedModel):
    subscription = models.ForeignKey(SaleSubscription, related_name="lines", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_unit = models.DecimalField(max_digits=15, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_ids = models.ManyToManyField(Tax, blank=True)
    def __str__(self): return f"SubLine {self.id} - {self.product.name}"

# Invoice
class AccountMove(TimeStampedModel):
    invoice_number = models.CharField(max_length=64, unique=True, null=True, blank=True)
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    subscription = models.ForeignKey(SaleSubscription, on_delete=models.PROTECT)
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT)
    date_invoice = models.DateField(default=timezone.now)
    state = models.CharField(max_length=20, default="draft")
    amount_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    invoice_origin = models.CharField(max_length=128, null=True, blank=True)
    pdf_attachment = models.FileField(upload_to="invoices/pdf/", null=True, blank=True)
    xml_attachment = models.FileField(upload_to="invoices/xml/", null=True, blank=True)
    qr_code_url = models.URLField(null=True, blank=True)
    def __str__(self): return f"Invoice #{self.invoice_number or self.id}"

class AccountMoveLine(TimeStampedModel):
    move = models.ForeignKey(AccountMove, related_name="lines", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_unit = models.DecimalField(max_digits=15, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_ids = models.ManyToManyField(Tax, blank=True)
    def __str__(self): return f"InvLine {self.id} - {self.product.name}"
