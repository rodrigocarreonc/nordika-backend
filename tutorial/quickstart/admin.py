from django.contrib import admin
from .models import Categoria, Mueble, Favorito, Proveedor, MovimientoInventario

admin.site.register(Categoria)
admin.site.register(Mueble)
admin.site.register(Favorito)
admin.site.register(Proveedor)
admin.site.register(MovimientoInventario)