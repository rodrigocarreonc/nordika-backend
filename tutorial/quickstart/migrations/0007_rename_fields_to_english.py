"""Renames fields and status values from Spanish to English, keeping all existing data."""

from django.conf import settings
from django.db import migrations

STATUS_MAP = {
    'PENDIENTE': 'PENDING',
    'ACEPTADO': 'ACCEPTED',
    'RECHAZADO': 'REJECTED',
    'CANCELADO': 'CANCELLED',
}


def statuses_to_english(apps, schema_editor):
    Reservation = apps.get_model('quickstart', 'Reservation')
    for old, new in STATUS_MAP.items():
        Reservation.objects.filter(status=old).update(status=new)


def statuses_to_spanish(apps, schema_editor):
    Reservation = apps.get_model('quickstart', 'Reservation')
    for old, new in STATUS_MAP.items():
        Reservation.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):

    dependencies = [
        ('quickstart', '0006_rename_models_to_english'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField('supplier', 'nombre', 'name'),
        migrations.RenameField('supplier', 'contacto', 'contact_name'),
        migrations.RenameField('supplier', 'telefono', 'phone'),
        migrations.RenameField('supplier', 'creado_en', 'created_at'),

        migrations.RenameField('category', 'nombre', 'name'),
        migrations.RenameField('category', 'descripcion', 'description'),

        migrations.RenameField('furniture', 'nombre', 'name'),
        migrations.RenameField('furniture', 'descripcion', 'description'),
        migrations.RenameField('furniture', 'precio', 'price'),
        migrations.RenameField('furniture', 'imagen', 'image'),
        migrations.RenameField('furniture', 'categoria', 'category'),
        migrations.RenameField('furniture', 'proveedor', 'supplier'),
        migrations.RenameField('furniture', 'creado_en', 'created_at'),
        migrations.RenameField('furniture', 'actualizado_en', 'updated_at'),

        migrations.RenameField('favorite', 'usuario', 'user'),
        migrations.RenameField('favorite', 'mueble', 'furniture'),
        migrations.RenameField('favorite', 'fecha_agregado', 'added_at'),

        migrations.RenameField('reservation', 'usuario', 'user'),
        migrations.RenameField('reservation', 'mueble', 'furniture'),
        migrations.RenameField('reservation', 'cantidad', 'quantity'),
        migrations.RenameField('reservation', 'estado', 'status'),
        migrations.RenameField('reservation', 'creado_en', 'created_at'),
        migrations.RenameField('reservation', 'actualizado_en', 'updated_at'),

        migrations.RenameField('sale', 'apartado', 'reservation'),
        migrations.RenameField('sale', 'precio_unitario', 'unit_price'),
        migrations.RenameField('sale', 'fecha_venta', 'sold_at'),

        migrations.RunPython(statuses_to_english, statuses_to_spanish),
    ]
