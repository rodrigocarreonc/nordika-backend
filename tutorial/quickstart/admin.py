"""Django Admin panel configuration to browse the catalog, inventory and audit data."""

from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Favorite, Furniture, Reservation, Sale, Supplier

admin.site.site_header = "Nordika Mueblería - Administración"
admin.site.site_title = "Nordika Admin"
admin.site.index_title = "Gestión del Catálogo e Inventario"


class FurnitureInline(admin.TabularInline):
    """Shows the related furniture inside a Supplier or Category page."""
    model = Furniture
    extra = 0
    fields = ('name', 'price', 'stock', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """Supplier administration with a count and an embedded list of its furniture."""
    list_display = ('id', 'name', 'contact_name', 'phone', 'email', 'furniture_total', 'created_at')
    search_fields = ('name', 'contact_name', 'email', 'phone')
    list_filter = ('created_at',)
    inlines = [FurnitureInline]

    @admin.display(description='Muebles Suministrados')
    def furniture_total(self, obj):
        return obj.furniture.count()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Category administration with a truncated description and the furniture total."""
    list_display = ('id', 'name', 'short_description', 'furniture_total')
    search_fields = ('name', 'description')
    inlines = [FurnitureInline]

    @admin.display(description='Descripción')
    def short_description(self, obj):
        if not obj.description:
            return "-"
        return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description

    @admin.display(description='Cantidad de Muebles')
    def furniture_total(self, obj):
        return obj.furniture.count()


@admin.register(Furniture)
class FurnitureAdmin(admin.ModelAdmin):
    """Inventory view with thumbnails, MXN price and a color-coded stock indicator."""
    list_display = (
        'id',
        'image_preview',
        'name',
        'category',
        'supplier',
        'formatted_price',
        'stock_badge',
        'favorites_total',
        'created_at'
    )
    list_filter = ('category', 'supplier', 'created_at')
    search_fields = ('name', 'description', 'category__name', 'supplier__name')
    list_editable = ()
    readonly_fields = ('large_image_preview', 'created_at', 'updated_at')

    fieldsets = (
        ('Información General', {
            'fields': ('name', 'description', 'category', 'supplier')
        }),
        ('Inventario y Precios', {
            'fields': ('price', 'stock')
        }),
        ('Multimedia', {
            'fields': ('image', 'large_image_preview')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Precio (MXN)', ordering='price')
    def formatted_price(self, obj):
        return f"${obj.price:,.2f}"

    # Traffic light: red sold out (0), amber low stock (<=3), green available.
    @admin.display(description='Stock', ordering='stock')
    def stock_badge(self, obj):
        if obj.stock == 0:
            color = "#dc2626"
            text = "Agotado (0)"
        elif obj.stock <= 3:
            color = "#d97706"
            text = f"Bajo stock ({obj.stock})"
        else:
            color = "#16a34a"
            text = f"En stock ({obj.stock})"
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{}</span>',
            color, text
        )

    @admin.display(description='Favoritos')
    def favorites_total(self, obj):
        return obj.favorites.count()

    @admin.display(description='Vista previa')
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 6px;" />', obj.image.url)
        return format_html('<span style="color: #9ca3af; font-size: 11px;">Sin imagen</span>')

    @admin.display(description='Imagen actual')
    def large_image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 250px; max-height: 250px; border-radius: 8px; object-fit: cover;" />', obj.image.url)
        return "No hay imagen cargada"


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Browse favorites saved by customers."""
    list_display = ('id', 'user', 'furniture', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username', 'user__email', 'furniture__name')
    readonly_fields = ('added_at',)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Read-only: create/accept/reject go through the API to keep stock and sales in sync."""
    list_display = ('code_display', 'user', 'furniture', 'quantity', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'furniture__name')

    @admin.display(description='Código')
    def code_display(self, obj):
        return obj.code

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """Read-only: sales are only created when a reservation is accepted through the API."""
    list_display = ('id', 'reservation', 'unit_price', 'total', 'sold_at')
    list_filter = ('sold_at',)
    search_fields = ('reservation__user__username', 'reservation__furniture__name')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
