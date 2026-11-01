from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Proveedor(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Mueble(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, default='')
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    stock = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    imagen = models.ImageField(upload_to='muebles/', null=True, blank=True)

    categoria = models.ForeignKey(
        Categoria,
        related_name='muebles',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    proveedor = models.ForeignKey(
        Proveedor,
        related_name='muebles',
        on_delete=models.PROTECT
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mueble'
        verbose_name_plural = 'Muebles'
        ordering = ['-creado_en']

    def __str__(self):
        cat_nombre = self.categoria.nombre if self.categoria else 'Sin categoría'
        return f"{self.nombre} ({cat_nombre}) - ${self.precio}"


class Favorito(models.Model):
    usuario = models.ForeignKey(
        User,
        related_name='favoritos',
        on_delete=models.CASCADE
    )
    mueble = models.ForeignKey(
        Mueble,
        related_name='favoritos',
        on_delete=models.CASCADE
    )
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Favorito'
        verbose_name_plural = 'Favoritos'
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

    mueble = models.ForeignKey(
        Mueble,
        related_name='movimientos',
        on_delete=models.CASCADE
    )
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Cantidad de artículos en el movimiento"
    )
    motivo = models.CharField(
        max_length=255,
        help_text="Ej. Compra al proveedor, Venta en tienda, Daño en almacén"
    )
    usuario = models.ForeignKey(
        User,
        related_name='movimientos_inventario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    fecha_movimiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-fecha_movimiento']

    def __str__(self):
        return f"{self.tipo_movimiento} de {self.cantidad} - {self.mueble.nombre}"
