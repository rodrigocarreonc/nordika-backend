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
            'password': 'Mueble$Azul47',
            'password_confirm': 'Mueble$Azul47',
            'first_name': 'Nuevo',
            'last_name': 'Cliente'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertTrue(User.objects.filter(username='nuevousuario').exists())

    def test_register_rechaza_password_debil(self):
        self.client.credentials()
        # Común, solo números, parecida al usuario y muy corta
        for password in ['password123', '12345678', 'debilusuario', 'Ab1!']:
            res = self.client.post('/api-register/', {
                'username': 'debilusuario', 'email': 'debil@nordika.com', 'password': password,
            })
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, password)
            self.assertIn('password', res.data)
        self.assertFalse(User.objects.filter(username='debilusuario').exists())

    def test_user_me_profile(self):
        response = self.client.get('/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')

        # Test PATCH me
        patch_response = self.client.patch('/me/', {'first_name': 'Actualizado'})
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['first_name'], 'Actualizado')

    def test_user_me_patch_invalid_email_format(self):
        # Correo inválido (formato erróneo) -> 400
        for invalid_email in ['hola', 'no-es-correo', 'usuario@', '@dominio.com', 'test@.com']:
            res = self.client.patch('/me/', {'email': invalid_email}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, f"Falló para: {invalid_email}")
            self.assertIn('email', res.data)

    def test_user_me_patch_email_non_text(self):
        # Correo no texto (número, lista, null) -> 400 (nunca 500!)
        non_text_values = [
            12345,
            ['correo@nordika.com'],
            {'correo': 'nordika'},
            None,
        ]
        for val in non_text_values:
            res = self.client.patch('/me/', {'email': val}, format='json')
            self.assertNotEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR, f"500 recibido para {val}")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, f"Falló para: {val}")
            self.assertIn('email', res.data)

    def test_user_me_patch_duplicate_email(self):
        # Correo duplicado -> 400
        User.objects.create_user(
            username='otro_usuario',
            email='otro@nordika.com',
            password='Mueble$Azul47'
        )
        # Intento de usar el mismo correo de otro usuario
        res = self.client.patch('/me/', {'email': 'otro@nordika.com'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', res.data)

        # Validación case-insensitive
        res_upper = self.client.patch('/me/', {'email': 'OTRO@NORDIKA.COM'}, format='json')
        self.assertEqual(res_upper.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', res_upper.data)

    def test_change_password(self):
        res = self.client.post('/change-password/', {'current_password': 'mala', 'new_password': 'nueva123'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        for debil in ['123', 'password123', '98765432']:
            res = self.client.post('/change-password/', {'current_password': 'testpassword123', 'new_password': debil}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, debil)
            self.assertTrue(res.data['detail'])

        res = self.client.post('/change-password/', {'current_password': 'testpassword123', 'new_password': 'nueva123'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotEqual(res.data['token'], self.token.key)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('nueva123'))
        # El token viejo ya no sirve
        self.assertEqual(self.client.get('/me/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_account(self):
        apartado = Apartado.objects.create(usuario=self.user, mueble=self.mueble, cantidad=3)
        Mueble.objects.filter(pk=self.mueble.pk).update(stock=7)

        res = self.client.delete('/me/', {'password': 'mala'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.get(pk=self.user.pk).is_active)

        res = self.client.delete('/me/', {'password': 'testpassword123'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        apartado.refresh_from_db()
        self.assertEqual(apartado.estado, Apartado.CANCELADO)
        # El staff ve el apartado marcado como de una cuenta eliminada
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=User.objects.create_user(username='admin_del', password='x', is_staff=True)).key)
        res = self.client.get(f'/apartados/{apartado.pk}/')
        self.assertFalse(res.data['usuario_activo'])
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 10)

        self.client.credentials()
        res = self.client.post('/api-token-auth/', {'username': 'testuser', 'password': 'testpassword123'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # El username y el email quedan libres para una cuenta nueva
        res = self.client.post('/api-register/', {
            'username': 'testuser', 'email': 'test@nordika.com', 'password': 'otra123',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_user_me_patch_empty_email(self):
        # Correo vacío -> 400
        for empty_val in ['', '   ']:
            res = self.client.patch('/me/', {'email': empty_val}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, f"Falló para: {repr(empty_val)}")
            self.assertIn('email', res.data)

    def test_user_me_patch_username_read_only(self):
        # Intento de cambiar username -> username no cambia
        res = self.client.patch('/me/', {'username': 'nuevo_username'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(res.data['username'], 'testuser')

    def test_user_me_patch_valid_update(self):
        # Actualización válida de first_name, last_name, email -> 200
        payload = {
            'first_name': 'NombreActualizado',
            'last_name': 'ApellidoActualizado',
            'email': '  NUEVO_CORREO@NORDIKA.COM  '
        }
        res = self.client.patch('/me/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'NombreActualizado')
        self.assertEqual(self.user.last_name, 'ApellidoActualizado')
        # Normalizado con strip().lower()
        self.assertEqual(self.user.email, 'nuevo_correo@nordika.com')

        self.assertEqual(res.data['first_name'], 'NombreActualizado')
        self.assertEqual(res.data['last_name'], 'ApellidoActualizado')
        self.assertEqual(res.data['email'], 'nuevo_correo@nordika.com')
        self.assertEqual(res.data['username'], 'testuser')

        # Actualizar con el mismo correo propio no genera error de duplicado
        res_same_email = self.client.patch('/me/', {'email': 'nuevo_correo@nordika.com'}, format='json')
        self.assertEqual(res_same_email.status_code, status.HTTP_200_OK)

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

    def test_categorias_y_proveedores_sin_paginacion(self):
        # Más de 100 (el máximo de page_size) para comprobar que llegan todos.
        Categoria.objects.bulk_create([Categoria(nombre=f'Cat {i:03}') for i in range(120)])
        Proveedor.objects.bulk_create([Proveedor(nombre=f'Prov {i:03}') for i in range(120)])
        for url, total in [('/categorias/', Categoria.objects.count()), ('/proveedores/', Proveedor.objects.count())]:
            response = self.client.get(f'{url}?page_size=10')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsInstance(response.data, list)
            self.assertEqual(len(response.data), total)
        # La búsqueda sigue funcionando sin paginación.
        response = self.client.get('/categorias/?search=Cat 119')
        self.assertEqual([c['nombre'] for c in response.data], ['Cat 119'])

    # 5. VALIDACIONES
    def test_mueble_validation_negative_price(self):
        self._admin_client()
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
        admin, _ = User.objects.get_or_create(username='admin_test', defaults={'is_staff': True})
        if not admin.is_staff:
            admin.is_staff = True
            admin.save()
        token, _ = Token.objects.get_or_create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

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

    def test_admin_no_puede_apartar(self):
        self._admin_client()
        res = self._apartar(2)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Apartado.objects.exists())
        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 10)

    def test_admin_filtra_activos_e_historial_de_todos(self):
        pendiente_id = self._apartar(1).data['id']
        resuelto_id = self._apartar(1).data['id']
        otro = User.objects.create_user('otro', password='x')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=otro).key)
        pendiente_otro_id = self._apartar(1).data['id']
        self._admin_client()
        self.client.post(f'/apartados/{resuelto_id}/rechazar/')

        activos = self.client.get('/apartados/', {'estado': 'PENDIENTE'}).data
        self.assertEqual({a['id'] for a in activos['results']}, {pendiente_id, pendiente_otro_id})
        historial = self.client.get('/apartados/', {'historial': 'true'}).data
        self.assertEqual([a['id'] for a in historial['results']], [resuelto_id])

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

    def test_cerrar_apartado_dos_veces_no_devuelve_stock_doble(self):
        # Simula dos peticiones que leyeron el mismo pendiente antes de que alguna lo cerrara
        apartado_id = self._apartar(3).data['id']
        lectura_1 = Apartado.objects.get(pk=apartado_id)
        lectura_2 = Apartado.objects.get(pk=apartado_id)

        self.assertTrue(lectura_1.cerrar(Apartado.CANCELADO))
        self.assertFalse(lectura_2.cerrar(Apartado.RECHAZADO))
        self.assertFalse(lectura_2.cerrar(Apartado.ACEPTADO))

        self.mueble.refresh_from_db()
        self.assertEqual(self.mueble.stock, 10)
        self.assertEqual(Apartado.objects.get(pk=apartado_id).estado, Apartado.CANCELADO)
        self.assertFalse(Venta.objects.filter(apartado_id=apartado_id).exists())

    def test_muebles_libera_stock_vencido(self):
        apartado_id = self._apartar(4).data['id']
        Apartado.objects.filter(pk=apartado_id).update(creado_en=timezone.now() - timedelta(days=6))
        res = self.client.get(f'/muebles/{self.mueble.id}/')
        self.assertEqual(res.data['stock'], 10)

    # 8. ELIMINACIÓN CON DEPENDENCIAS PROTEGIDAS (409 CONFLICT)
    def test_eliminar_proveedor_con_muebles_responde_409(self):
        self._admin_client()
        # self.proveedor tiene self.mueble asociado (1 mueble)
        res = self.client.delete(f'/proveedores/{self.proveedor.id}/')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data['detail'], 'No se puede eliminar: el proveedor tiene 1 mueble asociado.')
        self.assertTrue(Proveedor.objects.filter(id=self.proveedor.id).exists())

        # Si tiene más de un mueble asociado (plural)
        Mueble.objects.create(
            nombre='Mueble Extra',
            precio=Decimal('1500.00'),
            stock=2,
            categoria=self.categoria,
            proveedor=self.proveedor
        )
        res_plural = self.client.delete(f'/proveedores/{self.proveedor.id}/')
        self.assertEqual(res_plural.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res_plural.data['detail'], 'No se puede eliminar: el proveedor tiene 2 muebles asociados.')

    def test_eliminar_proveedor_sin_muebles_responde_204(self):
        self._admin_client()
        prov_sin_muebles = Proveedor.objects.create(nombre='Proveedor Sin Muebles')
        res = self.client.delete(f'/proveedores/{prov_sin_muebles.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Proveedor.objects.filter(id=prov_sin_muebles.id).exists())

    def test_eliminar_mueble_con_apartados_responde_409(self):
        # Crear un apartado asociado a self.mueble
        self._apartar(2)
        self._admin_client()
        res = self.client.delete(f'/muebles/{self.mueble.id}/')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data['detail'], 'No se puede eliminar: el mueble tiene 1 apartado asociado.')
        self.assertTrue(Mueble.objects.filter(id=self.mueble.id).exists())

        # Si tiene más de un apartado asociado (plural)
        # Cambiamos a cliente normal para crear el apartado y volvemos a admin
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self._apartar(1)
        self._admin_client()
        res_plural = self.client.delete(f'/muebles/{self.mueble.id}/')
        self.assertEqual(res_plural.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res_plural.data['detail'], 'No se puede eliminar: el mueble tiene 2 apartados asociados.')

    def test_eliminar_mueble_sin_apartados_responde_204(self):
        self._admin_client()
        mueble_sin_apartados = Mueble.objects.create(
            nombre='Mueble Sin Apartados',
            precio=Decimal('500.00'),
            stock=5,
            categoria=self.categoria,
            proveedor=self.proveedor
        )
        res = self.client.delete(f'/muebles/{mueble_sin_apartados.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Mueble.objects.filter(id=mueble_sin_apartados.id).exists())

    def test_eliminar_mueble_con_apartado_rechazado_responde_204(self):
        apartado_id = self._apartar(2).data['id']
        self._admin_client()
        self.client.post(f'/apartados/{apartado_id}/rechazar/')
        res = self.client.delete(f'/muebles/{self.mueble.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Mueble.objects.filter(id=self.mueble.id).exists())

    def test_eliminar_mueble_con_apartado_cancelado_responde_204(self):
        apartado_id = self._apartar(1).data['id']
        Apartado.objects.filter(id=apartado_id).update(estado=Apartado.CANCELADO)
        self._admin_client()
        res = self.client.delete(f'/muebles/{self.mueble.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Mueble.objects.filter(id=self.mueble.id).exists())

    def test_eliminar_mueble_con_apartado_aceptado_responde_409(self):
        apartado_id = self._apartar(1).data['id']
        self._admin_client()
        self.client.post(f'/apartados/{apartado_id}/aceptar/')
        res = self.client.delete(f'/muebles/{self.mueble.id}/')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data['detail'], 'No se puede eliminar: el mueble tiene 1 apartado asociado.')
        self.assertTrue(Mueble.objects.filter(id=self.mueble.id).exists())

    # 9. PERMISOS CRUD: SOLO STAFF PUEDE CREAR/EDITAR/ELIMINAR
    def test_usuario_no_staff_recibe_403_en_crud_proveedor_categoria_mueble(self):
        # Usuario normal autenticado (no staff)
        # Proveedores
        self.assertEqual(self.client.post('/proveedores/', {'nombre': 'Nuevo Prov'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f'/proveedores/{self.proveedor.id}/', {'nombre': 'Edit'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/proveedores/{self.proveedor.id}/').status_code, status.HTTP_403_FORBIDDEN)

        # Categorías
        self.assertEqual(self.client.post('/categorias/', {'nombre': 'Nueva Cat'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f'/categorias/{self.categoria.id}/', {'nombre': 'Edit'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/categorias/{self.categoria.id}/').status_code, status.HTTP_403_FORBIDDEN)

        # Muebles
        payload_mueble = {
            'nombre': 'Nuevo Mueble',
            'precio': '1200.00',
            'stock': 3,
            'proveedor_id': self.proveedor.id,
        }
        self.assertEqual(self.client.post('/muebles/', payload_mueble).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f'/muebles/{self.mueble.id}/', {'nombre': 'Edit'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/muebles/{self.mueble.id}/').status_code, status.HTTP_403_FORBIDDEN)

        # Pero SÍ puede leerlos (GET métodos seguros)
        self.assertEqual(self.client.get('/proveedores/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/categorias/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/muebles/').status_code, status.HTTP_200_OK)

        # Y puede usar acciones de cliente en muebles
        self.assertEqual(self.client.post(f'/muebles/{self.mueble.id}/toggle_favorito/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/muebles/mis_favoritos/').status_code, status.HTTP_200_OK)

    def test_usuario_staff_puede_hacer_crud_proveedor_categoria_mueble(self):
        self._admin_client()

        # Proveedor
        prov_res = self.client.post('/proveedores/', {'nombre': 'Proveedor Admin'})
        self.assertEqual(prov_res.status_code, status.HTTP_201_CREATED)
        prov_id = prov_res.data['id']
        patch_prov = self.client.patch(f'/proveedores/{prov_id}/', {'nombre': 'Proveedor Admin Edit'})
        self.assertEqual(patch_prov.status_code, status.HTTP_200_OK)
        del_prov = self.client.delete(f'/proveedores/{prov_id}/')
        self.assertEqual(del_prov.status_code, status.HTTP_204_NO_CONTENT)

        # Categoría
        cat_res = self.client.post('/categorias/', {'nombre': 'Categoría Admin'})
        self.assertEqual(cat_res.status_code, status.HTTP_201_CREATED)
        cat_id = cat_res.data['id']
        patch_cat = self.client.patch(f'/categorias/{cat_id}/', {'nombre': 'Categoría Admin Edit'})
        self.assertEqual(patch_cat.status_code, status.HTTP_200_OK)
        del_cat = self.client.delete(f'/categorias/{cat_id}/')
        self.assertEqual(del_cat.status_code, status.HTTP_204_NO_CONTENT)

        # Mueble
        mueble_res = self.client.post('/muebles/', {
            'nombre': 'Mueble Creado Por Staff',
            'descripcion': 'Descripción staff',
            'precio': '2500.00',
            'stock': 4,
            'proveedor_id': self.proveedor.id,
            'categoria_id': self.categoria.id,
        })
        self.assertEqual(mueble_res.status_code, status.HTTP_201_CREATED)
        mueble_id = mueble_res.data['id']
        patch_mueble = self.client.patch(f'/muebles/{mueble_id}/', {'nombre': 'Mueble Staff Editado'})
        self.assertEqual(patch_mueble.status_code, status.HTTP_200_OK)
        del_mueble = self.client.delete(f'/muebles/{mueble_id}/')
        self.assertEqual(del_mueble.status_code, status.HTTP_204_NO_CONTENT)

    # 10. APARTADOS CONTACTO & CREAR CLIENTE POR ADMIN
    def test_apartado_serializer_includes_usuario_contacto(self):
        self.user.first_name = 'Juan'
        self.user.last_name = 'Perez'
        self.user.email = 'juan.perez@nordika.com'
        self.user.save()

        res = self._apartar(1)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['usuario_username'], self.user.username)
        self.assertEqual(res.data['usuario_email'], 'juan.perez@nordika.com')
        self.assertEqual(res.data['usuario_nombre'], 'Juan Perez')

    def test_crear_cliente_admin_exitoso(self):
        self._admin_client()
        payload = {
            'username': 'cliente_nuevo',
            'email': 'nuevo_cliente@nordika.com',
            'password': 'Mueble$Azul47',
            'password_confirm': 'Mueble$Azul47',
            'first_name': 'Cliente',
            'last_name': 'Prueba'
        }
        res = self.client.post('/users/crear_cliente/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['username'], 'cliente_nuevo')
        self.assertEqual(res.data['email'], 'nuevo_cliente@nordika.com')
        self.assertEqual(res.data['first_name'], 'Cliente')
        self.assertEqual(res.data['last_name'], 'Prueba')
        self.assertFalse(res.data['is_staff'])

        nuevo = User.objects.get(username='cliente_nuevo')
        self.assertFalse(nuevo.is_staff)
        self.assertTrue(nuevo.check_password('Mueble$Azul47'))

    def test_crear_cliente_no_admin_recibe_403(self):
        payload = {
            'username': 'cliente_no_auth',
            'email': 'noauth@nordika.com',
            'password': 'Mueble$Azul47',
        }
        res = self.client.post('/users/crear_cliente/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_crear_cliente_validaciones(self):
        self._admin_client()
        # Contraseñas no coinciden
        res1 = self.client.post('/users/crear_cliente/', {
            'username': 'user1',
            'email': 'u1@nordika.com',
            'password': 'Mueble$Azul47',
            'password_confirm': 'diferente',
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Correo duplicado
        res2 = self.client.post('/users/crear_cliente/', {
            'username': 'user2',
            'email': self.user.email,
            'password': 'Mueble$Azul47',
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_crear_cliente_rutas_canonicas_sin_duplicados(self):
        self._admin_client()
        res_api = self.client.post('/api/users/crear_cliente/', {
            'username': 'cliente_api_prefix',
            'email': 'api_prefix@nordika.com',
            'password': 'Mueble$Azul47',
        }, format='json')
        self.assertEqual(res_api.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='cliente_api_prefix').exists())

