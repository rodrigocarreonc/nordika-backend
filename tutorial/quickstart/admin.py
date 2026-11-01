from django.contrib import admin
from django.utils.html import format_html
from .models import Categoria, Favorito, MovimientoInventario, Mueble, Proveedor

admin.site.site_header = "Nordika Mueblería - Administración"
admin.site.site_title = "Nordika Admin"
admin.site.index_title = "Gestión del Catálogo e Inventario"


class MuebleInline(admin.TabularInline):
    model = Mueble
    extra = 0
    fields = ('nombre', 'precio', 'stock', 'creado_en')
    readonly_fields = ('creado_en',)
    show_change_link = True


class MovimientoInventarioInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 0
    fields = ('tipo_movimiento', 'cantidad', 'motivo', 'usuario', 'fecha_movimiento')
    readonly_fields = ('fecha_movimiento',)
    can_delete = False


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'contacto', 'telefono', 'email', 'total_muebles', 'creado_en')
    search_fields = ('nombre', 'contacto', 'email', 'telefono')
    list_filter = ('creado_en',)
    inlines = [MuebleInline]

    def total_muebles(self, obj):
        return obj.muebles.count()
    total_muebles.short_description = 'Muebles Suministrados'


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'descripcion_corta', 'total_muebles')
    search_fields = ('nombre', 'descripcion')
    inlines = [MuebleInline]

    def descripcion_corta(self, obj):
        if not obj.descripcion:
            return "-"
        return obj.descripcion[:50] + "..." if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

    def total_muebles(self, obj):
        return obj.muebles.count()
    total_muebles.short_description = 'Cantidad de Muebles'


@admin.register(Mueble)
class MuebleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'imagen_preview',
        'nombre',
        'categoria',
        'proveedor',
        'precio_formateado',
        'stock_badge',
        'total_favoritos',
        'creado_en'
    )
    list_filter = ('categoria', 'proveedor', 'creado_en')
    search_fields = ('nombre', 'descripcion', 'categoria__nombre', 'proveedor__nombre')
    list_editable = ()
    readonly_fields = ('imagen_preview_grande', 'creado_en', 'actualizado_en')
    inlines = [MovimientoInventarioInline]

    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'descripcion', 'categoria', 'proveedor')
        }),
        ('Inventario y Precios', {
            'fields': ('precio', 'stock')
        }),
        ('Multimedia', {
            'fields': ('imagen', 'imagen_preview_grande')
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )

    def precio_formateado(self, obj):
        return f"${obj.precio:,.2f}"
    precio_formateado.short_description = 'Precio (MXN)'
    precio_formateado.admin_order_field = 'precio'

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
    stock_badge.short_description = 'Stock'
    stock_badge.admin_order_field = 'stock'

    def total_favoritos(self, obj):
        return obj.favoritos.count()
    total_favoritos.short_description = 'Favoritos'

    def imagen_preview(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 6px;" />', obj.imagen.url)
        return format_html('<span style="color: #9ca3af; font-size: 11px;">Sin imagen</span>')
    imagen_preview.short_description = 'Vista previa'

    def imagen_preview_grande(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="max-width: 250px; max-height: 250px; border-radius: 8px; object-fit: cover;" />', obj.imagen.url)
        return "No hay imagen cargada"
    imagen_preview_grande.short_description = 'Imagen actual'


@admin.register(Favorito)
class FavoritoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'mueble', 'fecha_agregado')
    list_filter = ('fecha_agregado',)
    search_fields = ('usuario__username', 'usuario__email', 'mueble__nombre')
    readonly_fields = ('fecha_agregado',)


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo_badge', 'mueble', 'cantidad', 'motivo', 'usuario', 'fecha_movimiento')
    list_filter = ('tipo_movimiento', 'fecha_movimiento')
    search_fields = ('mueble__nombre', 'motivo', 'usuario__username')
    readonly_fields = ('fecha_movimiento',)

    def tipo_badge(self, obj):
        colors = {
            'ENTRADA': '#16a34a',
            'SALIDA': '#dc2626',
            'AJUSTE': '#2563eb',
        }
        color = colors.get(obj.tipo_movimiento, '#4b5563')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color, obj.tipo_movimiento
        )
    tipo_badge.short_description = 'Tipo'
