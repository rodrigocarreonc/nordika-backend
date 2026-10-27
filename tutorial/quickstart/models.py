from django.db import models
from django.contrib.auth.models import User

class Proveedor(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class Mueble(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0) 
    imagen = models.ImageField(upload_to='muebles/', null=True, blank=True)
    
    # Relaciones
    categoria = models.ForeignKey(Categoria, related_name='muebles', on_delete=models.SET_NULL, null=True)
    proveedor = models.ForeignKey(Proveedor, related_name='muebles', on_delete=models.CASCADE)
    
    # Campos de auditoría
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} - {self.categoria.nombre if self.categoria else 'Sin categoría'}"

class Favorito(models.Model):
    usuario = models.ForeignKey(User, related_name='favoritos', on_delete=models.CASCADE)
    mueble = models.ForeignKey(Mueble, related_name='favoritado_por', on_delete=models.CASCADE)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'mueble')
        ordering = ['-fecha_agregado']

    def __str__(self):
        return f"{self.usuario.username} -> {self.mueble.nombre}"

class MovimientoInventario(models.Model):
    TIPO_CHOICES = [
        ('ENTRADA', 'Entrada (Compra/Devolución)'),
        ('SALIDA', 'Salida (Venta/Merma)'),
        ('AJUSTE', 'Ajuste de inventario'),
    ]

    mueble = models.ForeignKey(Mueble, related_name='movimientos', on_delete=models.CASCADE)
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.PositiveIntegerField(help_text="Cantidad de artículos en el movimiento")
    motivo = models.CharField(max_length=255, help_text="Ej. Compra al proveedor, Venta en app, Producto dañado")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_movimiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_movimiento']

    def __str__(self):
        return f"{self.tipo_movimiento} de {self.cantidad} - {self.mueble.nombre}"