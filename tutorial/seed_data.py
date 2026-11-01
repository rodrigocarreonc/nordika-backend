import os
import sys
from pathlib import Path

# Setup django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutorial.settings')

import django
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from tutorial.quickstart.models import Proveedor, Categoria, Mueble, Favorito, MovimientoInventario
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import io


def create_furniture_image(text, bg_color=(235, 230, 222), fg_color=(45, 55, 72)):
    """Generates an elegant minimalist placeholder image for furniture."""
    width, height = 600, 450
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Draw border and geometric accent (Scandinavian minimalist style)
    draw.rectangle([20, 20, width - 20, height - 20], outline=(200, 195, 185), width=2)
    draw.rectangle([40, 40, width - 40, 180], fill=(220, 215, 205))

    # Furniture icon silhouette (simple geometric couch/table representation)
    draw.rounded_rectangle([70, 70, width - 70, 150], radius=15, fill=(180, 175, 165))
    draw.rounded_rectangle([100, 100, width - 100, 160], radius=8, fill=(160, 155, 145))

    # Text
    draw.text((width // 2, 240), "NORDIKA", fill=(120, 105, 90), anchor="mm")
    draw.text((width // 2, 280), text, fill=fg_color, anchor="mm")
    draw.text((width // 2, 330), "Diseño Nórdico Minimalista", fill=(140, 140, 140), anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    return ContentFile(buffer.getvalue())


def seed():
    print("Iniciando creación de datos iniciales...")

    # 1. Usuarios
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
    print(f"Usuario admin listo: admin / admin123 (Token: {admin_user.auth_token.key})")

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
    print(f"Usuario cliente listo: gael / gael123 (Token: {customer_user.auth_token.key})")

    # 2. Proveedores
    proveedores_data = [
        {
            'nombre': 'Escandinavia Home Design',
            'contacto': 'Lars Jensen',
            'telefono': '+52 55 1234 5678',
            'email': 'contacto@escandinaviahome.com'
        },
        {
            'nombre': 'Maderas & Ensambles del Norte',
            'contacto': 'Sofía Villarreal',
            'telefono': '+52 81 8765 4321',
            'email': 'ventas@maderasdelnorte.mx'
        },
        {
            'nombre': 'Nordic Living Studio',
            'contacto': 'Henrik Lindqvist',
            'telefono': '+52 33 4567 8901',
            'email': 'pedidos@nordicliving.se'
        },
        {
            'nombre': 'Forja & Roble Artesanal',
            'contacto': 'Mateo Morales',
            'telefono': '+52 44 2345 6789',
            'email': 'taller@forjayroble.com'
        }
    ]

    prov_objs = {}
    for pdata in proveedores_data:
        obj, _ = Proveedor.objects.get_or_create(
            nombre=pdata['nombre'],
            defaults=pdata
        )
        prov_objs[pdata['nombre']] = obj
    print(f"{len(prov_objs)} Proveedores creados.")

    # 3. Categorías
    categorias_data = [
        {
            'nombre': 'Salas',
            'descripcion': 'Sofás, sillones lounge y mesas de centro de diseño nórdico.'
        },
        {
            'nombre': 'Comedores',
            'descripcion': 'Mesas de madera maciza, sillas ergonómicas y bufeteros.'
        },
        {
            'nombre': 'Recámaras',
            'descripcion': 'Camas plataforma, burós flotantes y cómodas minimalistas.'
        },
        {
            'nombre': 'Oficina & Estudio',
            'descripcion': 'Escritorios ergonómicos, libreros modulares y estanterías.'
        },
        {
            'nombre': 'Mesas & Consolas',
            'descripcion': 'Mesas auxiliares, consolas de recibidor y mesas nido.'
        }
    ]

    cat_objs = {}
    for cdata in categorias_data:
        obj, _ = Categoria.objects.get_or_create(
            nombre=cdata['nombre'],
            defaults=cdata
        )
        cat_objs[cdata['nombre']] = obj
    print(f"{len(cat_objs)} Categorías creadas.")

    # 4. Muebles
    muebles_data = [
        {
            'nombre': 'Sofá Oslo 3 Cuerpos Lino Gris',
            'descripcion': 'Elegante sofá tapizado en lino natural gris perla con patas cilíndricas en roble claro. Espuma de alta resiliencia y estructura de madera de abedul con ensambles reforzados.',
            'precio': Decimal('14999.00'),
            'stock': 8,
            'categoria': cat_objs['Salas'],
            'proveedor': prov_objs['Escandinavia Home Design'],
            'bg_color': (230, 232, 235),
        },
        {
            'nombre': 'Sillón Lounge Malmö Mostaza',
            'descripcion': 'Sillón individual con respaldo curvo envolvente, tapizado en terciopelo mostaza cálido y patas de madera maciza inclinadas estilo mid-century nórdico.',
            'precio': Decimal('6899.00'),
            'stock': 12,
            'categoria': cat_objs['Salas'],
            'proveedor': prov_objs['Nordic Living Studio'],
            'bg_color': (245, 238, 220),
        },
        {
            'nombre': 'Mesa de Comedor Estocolmo Roble',
            'descripcion': 'Mesa rectangular de 180x90cm elaborada en roble natural macizo tratado con aceite mate ecológico. Capacidad para 6 a 8 comensales con bordes suavizados.',
            'precio': Decimal('18499.00'),
            'stock': 5,
            'categoria': cat_objs['Comedores'],
            'proveedor': prov_objs['Maderas & Ensambles del Norte'],
            'bg_color': (238, 230, 218),
        },
        {
            'nombre': 'Juego de 4 Sillas Odense Gris Humo',
            'descripcion': 'Sillas nórdicas ergonómicas con carcasa de polipropileno mate y cojín integrado forrado en polipiel suave, sobre estructura de madera maciza de haya con tensores negros.',
            'precio': Decimal('7599.00'),
            'stock': 15,
            'categoria': cat_objs['Comedores'],
            'proveedor': prov_objs['Escandinavia Home Design'],
            'bg_color': (228, 230, 232),
        },
        {
            'nombre': 'Cama King Size Copenhague con Cabecera Tapizada',
            'descripcion': 'Base de cama flotante con somier de lamas de madera y cabecero acolchado en tejido bouclé arena. Diseñada para un descanso silencioso y ventilación óptima del colchón.',
            'precio': Decimal('22999.00'),
            'stock': 4,
            'categoria': cat_objs['Recámaras'],
            'proveedor': prov_objs['Forja & Roble Artesanal'],
            'bg_color': (240, 236, 230),
        },
        {
            'nombre': 'Buró Flotante Bergen Nogal',
            'descripcion': 'Mesita de noche de fijación oculta a muro con cajón de apertura push-to-open y repisa inferior para libros. Fabricado en chapa de nogal americano.',
            'precio': Decimal('3299.00'),
            'stock': 20,
            'categoria': cat_objs['Recámaras'],
            'proveedor': prov_objs['Maderas & Ensambles del Norte'],
            'bg_color': (225, 218, 210),
        },
        {
            'nombre': 'Escritorio Uppsala Roble & Acero Blanco',
            'descripcion': 'Escritorio minimalista de 120x60cm con cubierta de melamina texturizada de roble y estructura de perfiles de acero esmaltado en blanco satinado. Pasacables integrado.',
            'precio': Decimal('5499.00'),
            'stock': 10,
            'categoria': cat_objs['Oficina & Estudio'],
            'proveedor': prov_objs['Nordic Living Studio'],
            'bg_color': (235, 238, 240),
        },
        {
            'nombre': 'Librero Modular Lund 5 Niveles',
            'descripcion': 'Librero abierto asimétrico con repisas de profundidad variable. Perfecto como divisor de ambientes y organizador decorativo de libros y plantas.',
            'precio': Decimal('8999.00'),
            'stock': 6,
            'categoria': cat_objs['Oficina & Estudio'],
            'proveedor': prov_objs['Maderas & Ensambles del Norte'],
            'bg_color': (232, 228, 222),
        },
        {
            'nombre': 'Mesa de Centro Nido Gotemburgo (Set de 2)',
            'descripcion': 'Dúo de mesas bajas triangulares con bordes redondeados y patas cónicas en tres alturas. Acabado lacado blanco mate y chapa de haya natural.',
            'precio': Decimal('4299.00'),
            'stock': 14,
            'categoria': cat_objs['Mesas & Consolas'],
            'proveedor': prov_objs['Escandinavia Home Design'],
            'bg_color': (242, 240, 236),
        },
        {
            'nombre': 'Consola Recibidor Aarhus con Espejo Redondo',
            'descripcion': 'Consola delgada de 100cm de ancho con cajón central de tirador embutido y marco de espejo circular de 70cm a juego en madera maciza.',
            'precio': Decimal('6499.00'),
            'stock': 7,
            'categoria': cat_objs['Mesas & Consolas'],
            'proveedor': prov_objs['Forja & Roble Artesanal'],
            'bg_color': (234, 230, 224),
        },
        {
            'nombre': 'Credenza Helsinki 3 Puertas Ranuradas',
            'descripcion': 'Aparador buffet bajo con frontales de listones verticales y estantes internos ajustables. Ideal para salas de estar, comedores o recibidores espaciosos.',
            'precio': Decimal('16800.00'),
            'stock': 3,
            'categoria': cat_objs['Salas'],
            'proveedor': prov_objs['Nordic Living Studio'],
            'bg_color': (226, 220, 214),
        },
        {
            'nombre': 'Lámpara de Pie Tromsø Trípode Madera',
            'descripcion': 'Lámpara de pie de iluminación cálida difusa con pantalla cónica de lino crudo y trípode regulable de pino nórdico con cable trenzado textil.',
            'precio': Decimal('2899.00'),
            'stock': 18,
            'categoria': cat_objs['Salas'],
            'proveedor': prov_objs['Escandinavia Home Design'],
            'bg_color': (246, 244, 240),
        }
    ]

    muebles_creados = []
    for mdata in muebles_data:
        bg = mdata.pop('bg_color')
        mueble, created = Mueble.objects.get_or_create(
            nombre=mdata['nombre'],
            defaults=mdata
        )
        if created or not mueble.imagen:
            img_file = create_furniture_image(mueble.nombre, bg_color=bg)
            filename = f"mueble_{mueble.id}.jpg"
            mueble.imagen.save(filename, img_file, save=True)
        muebles_creados.append(mueble)

    print(f"{len(muebles_creados)} Muebles creados con imágenes.")

    # 5. Favoritos iniciales para usuario Gael
    Favorito.objects.get_or_create(usuario=customer_user, mueble=muebles_creados[0])
    Favorito.objects.get_or_create(usuario=customer_user, mueble=muebles_creados[1])
    Favorito.objects.get_or_create(usuario=customer_user, mueble=muebles_creados[4])
    print("Favoritos iniciales asociados a usuario 'gael'.")

    # 6. Movimientos de inventario iniciales
    movimientos_data = [
        ('ENTRADA', 10, 'Recepción de pedido inicial de fábrica', admin_user, muebles_creados[0]),
        ('SALIDA', 2, 'Venta en sala de exhibición', admin_user, muebles_creados[0]),
        ('ENTRADA', 15, 'Importación lote nórdico Dinamarca', admin_user, muebles_creados[1]),
        ('SALIDA', 3, 'Envío a cliente en Monterrey', admin_user, muebles_creados[1]),
        ('ENTRADA', 6, 'Llegada de taller de ebanistería', admin_user, muebles_creados[2]),
        ('AJUSTE', 5, 'Conteo físico mensual de almacén', admin_user, muebles_creados[2]),
    ]
    for tipo, cant, mot, usr, mueble in movimientos_data:
        MovimientoInventario.objects.get_or_create(
            mueble=mueble,
            tipo_movimiento=tipo,
            motivo=mot,
            defaults={
                'cantidad': cant,
                'usuario': usr
            }
        )
    print("Movimientos de inventario registrados.")
    print("¡Base de datos poblada exitosamente!")


if __name__ == '__main__':
    seed()
