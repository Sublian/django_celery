from django.contrib import admin
from .models import Partner, Company, Product, Tax, SaleSubscription, SaleSubscriptionLine, AccountMove, AccountMoveLine

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("id","name","email")

# similar para Company, Product, Tax ...
admin.site.register([Company, Product, Tax,AccountMove, AccountMoveLine])

@admin.register(SaleSubscription)
class SaleSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id","partner","date_start","date_end","state","company")
    search_fields = ("partner__name",)
    list_filter = ("state","company")

@admin.register(SaleSubscriptionLine)
class SaleSubscriptionLineAdmin(admin.ModelAdmin):
    list_display = ("id","subscription","product","quantity","price_unit")
    search_fields = ("subscription__name",)
    # list_filter = ("state","company")
# Registra demás modelos...
