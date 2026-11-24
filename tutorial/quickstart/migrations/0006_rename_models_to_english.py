"""Renames the models from Spanish to English (tables are renamed, data is kept)."""

from django.db import migrations


class Migration(migrations.Migration):
    # Field renames live in 0007: reversing model and FK field renames in one migration fails in Django.

    dependencies = [
        ('quickstart', '0005_apartado_estado_cancelado'),
    ]

    operations = [
        migrations.RenameModel('Venta', 'Sale'),
        migrations.RenameModel('Apartado', 'Reservation'),
        migrations.RenameModel('Favorito', 'Favorite'),
        migrations.RenameModel('Mueble', 'Furniture'),
        migrations.RenameModel('Categoria', 'Category'),
        migrations.RenameModel('Proveedor', 'Supplier'),
    ]
