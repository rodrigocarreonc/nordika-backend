"""Idempotent seed script that fills the local database with a catalog and demo accounts.

It runs on its own (`python tutorial/seed_data.py`) to have test data ready without
duplicating records when run more than once. Catalog text stays in Spanish because the app shows it.
"""

import os
import sys
from pathlib import Path

# Sets up Django manually because the script runs outside manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutorial.settings')

import django
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from tutorial.quickstart.models import Category, Favorite, Furniture, Supplier
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import io


def create_furniture_image(text, bg_color=(235, 230, 222), fg_color=(45, 55, 72)):
    """Generates an in-memory JPEG so the catalog does not depend on external URLs."""
    width, height = 600, 450
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Frame and minimalist geometric silhouette to tell the cards apart visually.
    draw.rectangle([20, 20, width - 20, height - 20], outline=(200, 195, 185), width=2)
    draw.rectangle([40, 40, width - 40, 180], fill=(220, 215, 205))
    draw.rounded_rectangle([70, 70, width - 70, 150], radius=15, fill=(180, 175, 165))
    draw.rounded_rectangle([100, 100, width - 100, 160], radius=8, fill=(160, 155, 145))

    draw.text((width // 2, 240), "NORDIKA", fill=(120, 105, 90), anchor="mm")
    draw.text((width // 2, 280), text, fill=fg_color, anchor="mm")
    draw.text((width // 2, 330), "Diseño Nórdico Minimalista", fill=(140, 140, 140), anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    return ContentFile(buffer.getvalue())


def seed():
    """Creates demo users, the initial catalog and favorites using get_or_create for idempotency."""
    print("Creating seed data...")

    # 1. Demo users (admin and customer) with known passwords and a pre-generated token.
    admin_user, _ = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@nordika.com',
            'is_staff': True,
            'is_superuser': True,
            'first_name': 'Administrador',
            'last_name': 'Nordika'
        }
    )
    admin_user.set_password('admin123')
    admin_user.save()
    Token.objects.get_or_create(user=admin_user)
    print(f"Admin user ready: admin / admin123 (Token: {admin_user.auth_token.key})")

    customer_user, _ = User.objects.get_or_create(
        username='gael',
        defaults={
            'email': 'gael@nordika.com',
            'is_staff': False,
            'is_superuser': False,
            'first_name': 'Gael',
            'last_name': 'Cliente'
        }
    )
    customer_user.set_password('gael123')
    customer_user.save()
    Token.objects.get_or_create(user=customer_user)
    print(f"Customer user ready: gael / gael123 (Token: {customer_user.auth_token.key})")

    # 2. Suppliers
    suppliers_data = [
        {
            'name': 'Escandinavia Home Design',
            'contact_name': 'Lars Jensen',
            'phone': '+52 55 1234 5678',
            'email': 'contacto@escandinaviahome.com'
        },
        {
            'name': 'Maderas & Ensambles del Norte',
            'contact_name': 'Sofía Villarreal',
            'phone': '+52 81 8765 4321',
            'email': 'ventas@maderasdelnorte.mx'
        },
        {
            'name': 'Nordic Living Studio',
            'contact_name': 'Henrik Lindqvist',
            'phone': '+52 33 4567 8901',
            'email': 'pedidos@nordicliving.se'
        },
        {
            'name': 'Forja & Roble Artesanal',
            'contact_name': 'Mateo Morales',
            'phone': '+52 44 2345 6789',
            'email': 'taller@forjayroble.com'
        }
    ]

    suppliers = {}
    for data in suppliers_data:
        obj, _ = Supplier.objects.get_or_create(
            name=data['name'],
            defaults=data
        )
        suppliers[data['name']] = obj
    print(f"{len(suppliers)} suppliers created.")

    # 3. Categories
    categories_data = [
        {
            'name': 'Salas',
            'description': 'Sofás, sillones lounge y mesas de centro de diseño nórdico.'
        },
        {
            'name': 'Comedores',
            'description': 'Mesas de madera maciza, sillas ergonómicas y bufeteros.'
        },
        {
            'name': 'Recámaras',
            'description': 'Camas plataforma, burós flotantes y cómodas minimalistas.'
        },
        {
            'name': 'Oficina & Estudio',
            'description': 'Escritorios ergonómicos, libreros modulares y estanterías.'
        },
        {
            'name': 'Mesas & Consolas',
            'description': 'Mesas auxiliares, consolas de recibidor y mesas nido.'
        }
    ]

    categories = {}
    for data in categories_data:
        obj, _ = Category.objects.get_or_create(
            name=data['name'],
            defaults=data
        )
        categories[data['name']] = obj
    print(f"{len(categories)} categories created.")

    # 4. Furniture
    furniture_data = [
        {
            'name': 'Sofá Oslo 3 Cuerpos Lino Gris',
            'description': 'Elegante sofá tapizado en lino natural gris perla con patas cilíndricas en roble claro. Espuma de alta resiliencia y estructura de madera de abedul con ensambles reforzados.',
            'price': Decimal('14999.00'),
            'stock': 8,
            'category': categories['Salas'],
            'supplier': suppliers['Escandinavia Home Design'],
            'bg_color': (230, 232, 235),
        },
        {
            'name': 'Sillón Lounge Malmö Mostaza',
            'description': 'Sillón individual con respaldo curvo envolvente, tapizado en terciopelo mostaza cálido y patas de madera maciza inclinadas estilo mid-century nórdico.',
            'price': Decimal('6899.00'),
            'stock': 12,
            'category': categories['Salas'],
            'supplier': suppliers['Nordic Living Studio'],
            'bg_color': (245, 238, 220),
        },
        {
            'name': 'Mesa de Comedor Estocolmo Roble',
            'description': 'Mesa rectangular de 180x90cm elaborada en roble natural macizo tratado con aceite mate ecológico. Capacidad para 6 a 8 comensales con bordes suavizados.',
            'price': Decimal('18499.00'),
            'stock': 5,
            'category': categories['Comedores'],
            'supplier': suppliers['Maderas & Ensambles del Norte'],
            'bg_color': (238, 230, 218),
        },
        {
            'name': 'Juego de 4 Sillas Odense Gris Humo',
            'description': 'Sillas nórdicas ergonómicas con carcasa de polipropileno mate y cojín integrado forrado en polipiel suave, sobre estructura de madera maciza de haya con tensores negros.',
            'price': Decimal('7599.00'),
            'stock': 15,
            'category': categories['Comedores'],
            'supplier': suppliers['Escandinavia Home Design'],
            'bg_color': (228, 230, 232),
        },
        {
            'name': 'Cama King Size Copenhague con Cabecera Tapizada',
            'description': 'Base de cama flotante con somier de lamas de madera y cabecero acolchado en tejido bouclé arena. Diseñada para un descanso silencioso y ventilación óptima del colchón.',
            'price': Decimal('22999.00'),
            'stock': 4,
            'category': categories['Recámaras'],
            'supplier': suppliers['Forja & Roble Artesanal'],
            'bg_color': (240, 236, 230),
        },
        {
            'name': 'Buró Flotante Bergen Nogal',
            'description': 'Mesita de noche de fijación oculta a muro con cajón de apertura push-to-open y repisa inferior para libros. Fabricado en chapa de nogal americano.',
            'price': Decimal('3299.00'),
            'stock': 20,
            'category': categories['Recámaras'],
            'supplier': suppliers['Maderas & Ensambles del Norte'],
            'bg_color': (225, 218, 210),
        },
        {
            'name': 'Escritorio Uppsala Roble & Acero Blanco',
            'description': 'Escritorio minimalista de 120x60cm con cubierta de melamina texturizada de roble y estructura de perfiles de acero esmaltado en blanco satinado. Pasacables integrado.',
            'price': Decimal('5499.00'),
            'stock': 10,
            'category': categories['Oficina & Estudio'],
            'supplier': suppliers['Nordic Living Studio'],
            'bg_color': (235, 238, 240),
        },
        {
            'name': 'Librero Modular Lund 5 Niveles',
            'description': 'Librero abierto asimétrico con repisas de profundidad variable. Perfecto como divisor de ambientes y organizador decorativo de libros y plantas.',
            'price': Decimal('8999.00'),
            'stock': 6,
            'category': categories['Oficina & Estudio'],
            'supplier': suppliers['Maderas & Ensambles del Norte'],
            'bg_color': (232, 228, 222),
        },
        {
            'name': 'Mesa de Centro Nido Gotemburgo (Set de 2)',
            'description': 'Dúo de mesas bajas triangulares con bordes redondeados y patas cónicas en tres alturas. Acabado lacado blanco mate y chapa de haya natural.',
            'price': Decimal('4299.00'),
            'stock': 14,
            'category': categories['Mesas & Consolas'],
            'supplier': suppliers['Escandinavia Home Design'],
            'bg_color': (242, 240, 236),
        },
        {
            'name': 'Consola Recibidor Aarhus con Espejo Redondo',
            'description': 'Consola delgada de 100cm de ancho con cajón central de tirador embutido y marco de espejo circular de 70cm a juego en madera maciza.',
            'price': Decimal('6499.00'),
            'stock': 7,
            'category': categories['Mesas & Consolas'],
            'supplier': suppliers['Forja & Roble Artesanal'],
            'bg_color': (234, 230, 224),
        },
        {
            'name': 'Credenza Helsinki 3 Puertas Ranuradas',
            'description': 'Aparador buffet bajo con frontales de listones verticales y estantes internos ajustables. Ideal para salas de estar, comedores o recibidores espaciosos.',
            'price': Decimal('16800.00'),
            'stock': 3,
            'category': categories['Salas'],
            'supplier': suppliers['Nordic Living Studio'],
            'bg_color': (226, 220, 214),
        },
        {
            'name': 'Lámpara de Pie Tromsø Trípode Madera',
            'description': 'Lámpara de pie de iluminación cálida difusa con pantalla cónica de lino crudo y trípode regulable de pino nórdico con cable trenzado textil.',
            'price': Decimal('2899.00'),
            'stock': 18,
            'category': categories['Salas'],
            'supplier': suppliers['Escandinavia Home Design'],
            'bg_color': (246, 244, 240),
        }
    ]

    created_furniture = []
    for data in furniture_data:
        bg = data.pop('bg_color')
        furniture, created = Furniture.objects.get_or_create(
            name=data['name'],
            defaults=data
        )
        if created or not furniture.image:
            img_file = create_furniture_image(furniture.name, bg_color=bg)
            filename = f"furniture_{furniture.id}.jpg"
            furniture.image.save(filename, img_file, save=True)
        created_furniture.append(furniture)

    print(f"{len(created_furniture)} furniture items created with images.")

    # 5. Initial favorites for the 'gael' user
    Favorite.objects.get_or_create(user=customer_user, furniture=created_furniture[0])
    Favorite.objects.get_or_create(user=customer_user, furniture=created_furniture[1])
    Favorite.objects.get_or_create(user=customer_user, furniture=created_furniture[4])
    print("Initial favorites linked to the 'gael' user.")

    print("Database seeded successfully!")


if __name__ == '__main__':
    seed()
