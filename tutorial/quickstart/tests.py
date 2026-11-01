from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Categoria, Favorito, MovimientoInventario, Mueble, Proveedor


class NordikaBackendTests(APITestCase):
    def setUp(self):
        # Crear usuarios
        self.user = User.objects.create_user(
            username='testuser',
            email='test@nordika.com',
            password='testpassword123',
            first_name='Test',
            last_name='User'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # Crear proveedor y categoría
        self.proveedor = Proveedor.objects.create(
            nombre='Taller Nórdico Test',
            contacto='Hans',
            telefono='12345678',
            email='hans@nordic.com'
        )
        self.categoria = Categoria.objects.create(
            nombre='Salas Test',
            descripcion='Categoría para pruebas de salas'
        )

        # Crear mueble
        self.mueble = Mueble.objects.create(
            nombre='Sofá Test Nórdico',
            descripcion='Sofá de prueba',
            precio=Decimal('9999.00'),
            stock=10,
            categoria=self.categoria,
            proveedor=self.proveedor
        )

    # 1. AUTENTICACIÓN
    def test_login_success(self):
        self.client.credentials()  # Sin token previo
        response = self.client.post('/api-token-auth/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['username'], 'testuser')

    def test_register_user(self):
        self.client.credentials()
        response = self.client.post('/api-register/', {
            'username': 'nuevousuario',
            'email': 'nuevo@nordika.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'first_name': 'Nuevo',
            'last_name': 'Cliente'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertTrue(User.objects.filter(username='nuevousuario').exists())

    def test_user_me_profile(self):
        response = self.client.get('/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')

        # Test PATCH me
        patch_response = self.client.patch('/me/', {'first_name': 'Actualizado'})
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['first_name'], 'Actualizado')

    def test_logout(self):
        response = self.client.post('/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Token should be deleted
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_reset_token(self):
        old_token = self.token.key
        response = self.client.post('/reset-token/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertNotEqual(response.data['token'], old_token)

    # 2. MODELOS Y RELACIONES & 4. SERIALIZERS ANIDADOS
    def test_mueble_nested_serializer(self):
        response = self.client.get(f'/muebles/{self.mueble.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('categoria', response.data)
        self.assertEqual(response.data['categoria']['nombre'], 'Salas Test')
        self.assertIn('proveedor', response.data)
        self.assertEqual(response.data['proveedor']['nombre'], 'Taller Nórdico Test')
        self.assertIn('is_favorito', response.data)
        self.assertFalse(response.data['is_favorito'])

    # 3. BÚSQUEDA Y FILTROS
    def test_muebles_search_and_filter(self):
        response = self.client.get('/muebles/?search=Nórdico')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

        # Filtro por categoría
        cat_response = self.client.get(f'/muebles/?categoria={self.categoria.id}')
        self.assertEqual(cat_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cat_response.data['count'], 1)

        # Filtro por precio
        price_response = self.client.get('/muebles/?precio_min=10000')
        self.assertEqual(price_response.status_code, status.HTTP_200_OK)
        self.assertEqual(price_response.data['count'], 0)

    # 4. PAGINACIÓN CONFIGURABLE
    def test_configurable_pagination(self):
        response = self.client.get('/muebles/?page_size=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page_size'], 2)
        self.assertIn('results', response.data)
        self.assertIn('total_pages', response.data)

    # 5. VALIDACIONES
    def test_mueble_validation_negative_price(self):
        response = self.client.post('/muebles/', {
            'nombre': 'Mueble Inválido',
            'descripcion': 'Test',
            'precio': '-50.00',
            'stock': 5,
            'proveedor_id': self.proveedor.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 6. CUSTOM ACTIONS (Favoritos & Movimiento Inventario)
    def test_toggle_favorito(self):
        # Toggle ON
        toggle_res = self.client.post(f'/muebles/{self.mueble.id}/toggle_favorito/')
        self.assertEqual(toggle_res.status_code, status.HTTP_200_OK)
        self.assertTrue(toggle_res.data['is_favorito'])
        self.assertTrue(Favorito.objects.filter(usuario=self.user, mueble=self.mueble).exists())

        # Check mis_favoritos
        mis_favs = self.client.get('/muebles/mis_favoritos/')
        self.assertEqual(mis_favs.status_code, status.HTTP_200_OK)
        self.assertEqual(mis_favs.data['count'], 1)

        # Toggle OFF
        toggle_res2 = self.client.post(f'/muebles/{self.mueble.id}/toggle_favorito/')
        self.assertEqual(toggle_res2.status_code, status.HTTP_200_OK)
        self.assertFalse(toggle_res2.data['is_favorito'])

    def test_registrar_movimiento_inventario(self):
        initial_stock = self.mueble.stock
        # Entrada
        res = self.client.post(f'/muebles/{self.mueble.id}/registrar_movimiento/', {
            'tipo_movimiento': 'ENTRADA',
            'cantidad': 5,
            'motivo': 'Compra de reposición'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, initial_stock + 5)

        # Salida con stock insuficiente falla
        res_fail = self.client.post(f'/muebles/{self.mueble.id}/registrar_movimiento/', {
            'tipo_movimiento': 'SALIDA',
            'cantidad': 999,
            'motivo': 'Venta excesiva'
        })
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)
