from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Apartado, Categoria, Favorito, Mueble, Proveedor, Venta


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

    # 6. CUSTOM ACTIONS (Favoritos)
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

    def test_get_requires_token(self):
        self.client.credentials()
        for url in ['/muebles/', '/muebles/destacados/', '/categorias/', '/proveedores/']:
            self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED, url)

    # 7. APARTADOS
    def _admin_client(self):
        admin = User.objects.create_user('admin_test', password='x', is_staff=True)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=admin).key)

    def _apartar(self, cantidad):
        return self.client.post('/apartados/', {'mueble_id': self.mueble.id, 'cantidad': cantidad})

    def test_apartado_descuenta_stock(self):
        res = self._apartar(3)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['estado'], 'PENDIENTE')
        self.assertEqual(res.data['codigo'], f"APT-{res.data['id']}")
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 7)

    def test_apartado_stock_insuficiente(self):
        self.assertEqual(self._apartar(11).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._apartar(0).status_code, status.HTTP_400_BAD_REQUEST)
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 10)

    def test_usuario_no_puede_aceptar_ni_ver_ajenos(self):
        apartado_id = self._apartar(2).data['id']
        self.assertEqual(self.client.post(f'/apartados/{apartado_id}/aceptar/').status_code, status.HTTP_403_FORBIDDEN)
        otro = User.objects.create_user('otro', password='x')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=otro).key)
        self.assertEqual(self.client.get(f'/apartados/{apartado_id}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_aceptar_registra_venta(self):
        apartado_id = self._apartar(2).data['id']
        self._admin_client()
        res = self.client.post(f'/apartados/{apartado_id}/aceptar/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['estado'], 'ACEPTADO')
        venta = Venta.objects.get(apartado_id=apartado_id)
        self.assertEqual(venta.total, Decimal('19998.00'))
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 8)
        # No se puede resolver dos veces
        self.assertEqual(self.client.post(f'/apartados/{apartado_id}/rechazar/').status_code, status.HTTP_400_BAD_REQUEST)

    def test_rechazar_libera_stock(self):
        apartado_id = self._apartar(4).data['id']
        self._admin_client()
        res = self.client.post(f'/apartados/{apartado_id}/rechazar/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['estado'], 'RECHAZADO')
        self.assertFalse(Venta.objects.filter(apartado_id=apartado_id).exists())
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 10)

    def test_apartado_expira_a_los_5_dias(self):
        res = self._apartar(3)
        apartado_id = res.data['id']
        creado = Apartado.objects.get(pk=apartado_id).creado_en
        self.assertEqual(datetime.fromisoformat(res.data['expira_en']), creado + timedelta(days=5))

        # Aún vigente: no se cancela
        Apartado.objects.filter(pk=apartado_id).update(creado_en=timezone.now() - timedelta(days=4, hours=23))
        self.assertEqual(self.client.get(f'/apartados/{apartado_id}/').data['estado'], 'PENDIENTE')

        # Vencido: se cancela y libera el stock
        Apartado.objects.filter(pk=apartado_id).update(creado_en=timezone.now() - timedelta(days=5, minutes=1))
        res = self.client.get(f'/apartados/{apartado_id}/')
        self.assertEqual(res.data['estado'], 'CANCELADO')
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 10)

        # Ya no se puede aceptar
        self._admin_client()
        self.assertEqual(self.client.post(f'/apartados/{apartado_id}/aceptar/').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Venta.objects.filter(apartado_id=apartado_id).exists())

    def test_muebles_libera_stock_vencido(self):
        apartado_id = self._apartar(4).data['id']
        Apartado.objects.filter(pk=apartado_id).update(creado_en=timezone.now() - timedelta(days=6))
        res = self.client.get(f'/muebles/{self.mueble.id}/')
        self.assertEqual(res.data['stock'], 10)
