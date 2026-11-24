"""Modelos de dominio del catálogo, favoritos, apartados e historial de ventas."""

from datetime import timedelta
from decimal import Decimal
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Proveedor(models.Model):
    """Fabricante o distribuidor de muebles; su nombre es único para evitar duplicados en catálogo."""
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
    """Agrupación lógica del catálogo (Salas, Comedores, etc.) usada en filtros de la app."""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Mueble(models.Model):
    """Articulo principal del inventario con precio positivo, existencias y relaciones al catálogo."""
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

    # SET_NULL permite borrar una categoría sin perder sus muebles; quedan "Sin categoría".
    categoria = models.ForeignKey(
        Categoria,
        related_name='muebles',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    # PROTECT impide borrar un proveedor que aún tiene muebles asignados (la API devuelve 409).
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
    """Relación única usuario-mueble; CASCADE limpia automáticamente favoritos de cuentas o muebles borrados."""
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


class Apartado(models.Model):
    """Reserva temporal de stock hecha por un cliente; vence a los 5 días si el staff no la resuelve."""
    PENDIENTE = 'PENDIENTE'
    ACEPTADO = 'ACEPTADO'
    RECHAZADO = 'RECHAZADO'
    CANCELADO = 'CANCELADO'
    ESTADO_CHOICES = [
        (PENDIENTE, 'Pendiente'),
        (ACEPTADO, 'Aceptado'),
        (RECHAZADO, 'Rechazado'),
        (CANCELADO, 'Cancelado (vencido)'),
    ]
    DIAS_VIGENCIA = 5

    usuario = models.ForeignKey(
        User,
        related_name='apartados',
        on_delete=models.CASCADE
    )
    # PROTECT evita apartados huérfanos (mueble=null) en el historial y en las respuestas de la API.
    mueble = models.ForeignKey(
        Mueble,
        related_name='apartados',
        on_delete=models.PROTECT
    )
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=PENDIENTE)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Apartado'
        verbose_name_plural = 'Apartados'
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.codigo} - {self.usuario.username} aparta {self.cantidad} x {self.mueble.nombre} ({self.estado})"

    @property
    def codigo(self):
        return f"APT-{self.id}"

    @property
    def expira_en(self):
        return self.creado_en + timedelta(days=self.DIAS_VIGENCIA)

    def cerrar(self, nuevo_estado):
        """
        Pasa el apartado de PENDIENTE a nuevo_estado: registra la venta si se acepta o devuelve
        la cantidad al stock si no. Regresa False si otra petición ya lo había cerrado.
        """
        # El UPDATE condicional es el candado: SQLite ignora select_for_update y dos
        # peticiones podían leer el mismo pendiente y devolver su stock dos veces.
        with transaction.atomic():
            cerrado = Apartado.objects.filter(pk=self.pk, estado=self.PENDIENTE).update(
                estado=nuevo_estado, actualizado_en=timezone.now()
            )
            if not cerrado:
                return False
            if nuevo_estado == self.ACEPTADO:
                precio = self.mueble.precio
                Venta.objects.create(apartado=self, precio_unitario=precio, total=precio * self.cantidad)
            else:
                Mueble.objects.filter(pk=self.mueble_id).update(stock=F('stock') + self.cantidad)
        self.refresh_from_db(fields=['estado', 'actualizado_en'])
        return True

    @classmethod
    def cancelar_vencidos(cls):
        """Cancela los apartados pendientes con más de DIAS_VIGENCIA días y devuelve su cantidad al stock."""
        limite = timezone.now() - timedelta(days=cls.DIAS_VIGENCIA)
        vencidos = cls.objects.filter(estado=cls.PENDIENTE, creado_en__lte=limite)
        return sum(apartado.cerrar(cls.CANCELADO) for apartado in vencidos)


class Venta(models.Model):
    """Registro inmutable generado al aceptar un apartado; congela el precio del mueble en ese momento."""
    # PROTECT resguarda el historial contable impidiendo borrar el apartado o mueble vendido.
    apartado = models.OneToOneField(
        Apartado,
        related_name='venta',
        on_delete=models.PROTECT
    )
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_venta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_venta']

    def __str__(self):
        return f"Venta #{self.id} - {self.apartado.mueble.nombre} - ${self.total}"
