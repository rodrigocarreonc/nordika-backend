"""Domain models for the catalog, favorites, reservations and sales history."""

from datetime import timedelta
from decimal import Decimal
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Supplier(models.Model):
    """Furniture manufacturer or distributor; the name is unique to avoid catalog duplicates."""
    name = models.CharField('nombre', max_length=150, unique=True)
    contact_name = models.CharField('contacto', max_length=100, blank=True, null=True)
    phone = models.CharField('teléfono', max_length=20, blank=True, null=True)
    email = models.EmailField('correo', blank=True, null=True)
    created_at = models.DateTimeField('creado en', auto_now_add=True)

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']

    def __str__(self):
        return self.name


class Category(models.Model):
    """Logical catalog grouping (living rooms, dining rooms, etc.) used by the app filters."""
    name = models.CharField('nombre', max_length=100, unique=True)
    description = models.TextField('descripción', blank=True, null=True)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['name']

    def __str__(self):
        return self.name


class Furniture(models.Model):
    """Main inventory item with a positive price, stock and catalog relations."""
    name = models.CharField('nombre', max_length=150)
    description = models.TextField('descripción', blank=True, default='')
    price = models.DecimalField(
        'precio',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    stock = models.PositiveIntegerField(
        'stock',
        default=0,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField('imagen', upload_to='furniture/', null=True, blank=True)

    # SET_NULL lets a category be deleted without losing its furniture; they become "Sin categoría".
    category = models.ForeignKey(
        Category,
        verbose_name='categoría',
        related_name='furniture',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    # PROTECT blocks deleting a supplier that still has furniture assigned (the API returns 409).
    supplier = models.ForeignKey(
        Supplier,
        verbose_name='proveedor',
        related_name='furniture',
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField('creado en', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado en', auto_now=True)

    class Meta:
        verbose_name = 'Mueble'
        verbose_name_plural = 'Muebles'
        ordering = ['-created_at']

    def __str__(self):
        category_name = self.category.name if self.category else 'Sin categoría'
        return f"{self.name} ({category_name}) - ${self.price}"


class Favorite(models.Model):
    """Unique user-furniture pair; CASCADE cleans up favorites of deleted accounts or furniture."""
    user = models.ForeignKey(
        User,
        verbose_name='usuario',
        related_name='favorites',
        on_delete=models.CASCADE
    )
    furniture = models.ForeignKey(
        Furniture,
        verbose_name='mueble',
        related_name='favorites',
        on_delete=models.CASCADE
    )
    added_at = models.DateTimeField('fecha agregado', auto_now_add=True)

    class Meta:
        verbose_name = 'Favorito'
        verbose_name_plural = 'Favoritos'
        unique_together = ('user', 'furniture')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} -> {self.furniture.name}"


class Reservation(models.Model):
    """Temporary stock hold made by a customer; it expires after 5 days if staff does not resolve it."""
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    REJECTED = 'REJECTED'
    CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (PENDING, 'Pendiente'),
        (ACCEPTED, 'Aceptado'),
        (REJECTED, 'Rechazado'),
        (CANCELLED, 'Cancelado (vencido)'),
    ]
    VALID_DAYS = 5

    user = models.ForeignKey(
        User,
        verbose_name='usuario',
        related_name='reservations',
        on_delete=models.CASCADE
    )
    # PROTECT avoids orphan reservations (furniture=null) in the history and in API responses.
    furniture = models.ForeignKey(
        Furniture,
        verbose_name='mueble',
        related_name='reservations',
        on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField('cantidad', validators=[MinValueValidator(1)])
    status = models.CharField('estado', max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField('creado en', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado en', auto_now=True)

    class Meta:
        verbose_name = 'Apartado'
        verbose_name_plural = 'Apartados'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.code} - {self.user.username} aparta {self.quantity} x "
            f"{self.furniture.name} ({self.get_status_display()})"
        )

    @property
    def code(self):
        # "APT" (apartado) is the code customers see in the app.
        return f"APT-{self.id}"

    @property
    def expires_at(self):
        return self.created_at + timedelta(days=self.VALID_DAYS)

    def close(self, new_status):
        """
        Moves the reservation from PENDING to new_status: records the sale when accepted or
        returns the quantity to stock otherwise. Returns False if another request already closed it.
        """
        # The conditional UPDATE is the lock: SQLite ignores select_for_update and two
        # requests could read the same pending reservation and return its stock twice.
        with transaction.atomic():
            closed = Reservation.objects.filter(pk=self.pk, status=self.PENDING).update(
                status=new_status, updated_at=timezone.now()
            )
            if not closed:
                return False
            if new_status == self.ACCEPTED:
                price = self.furniture.price
                Sale.objects.create(reservation=self, unit_price=price, total=price * self.quantity)
            else:
                Furniture.objects.filter(pk=self.furniture_id).update(stock=F('stock') + self.quantity)
        self.refresh_from_db(fields=['status', 'updated_at'])
        return True

    @classmethod
    def cancel_expired(cls):
        """Cancels pending reservations older than VALID_DAYS days and returns their quantity to stock."""
        limit = timezone.now() - timedelta(days=cls.VALID_DAYS)
        expired = cls.objects.filter(status=cls.PENDING, created_at__lte=limit)
        return sum(reservation.close(cls.CANCELLED) for reservation in expired)


class Sale(models.Model):
    """Immutable record created when a reservation is accepted; freezes the furniture price at that moment."""
    # PROTECT keeps the accounting history by blocking deletion of the sold reservation or furniture.
    reservation = models.OneToOneField(
        Reservation,
        verbose_name='apartado',
        related_name='sale',
        on_delete=models.PROTECT
    )
    unit_price = models.DecimalField('precio unitario', max_digits=10, decimal_places=2)
    total = models.DecimalField('total', max_digits=12, decimal_places=2)
    sold_at = models.DateTimeField('fecha de venta', auto_now_add=True)

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-sold_at']

    def __str__(self):
        return f"Venta #{self.id} - {self.reservation.furniture.name} - ${self.total}"
