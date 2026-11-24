"""REST API integration test suite (auth, catalog, reservations, concurrency and permissions)."""

from datetime import datetime, timedelta
from decimal import Decimal
import tempfile
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Category, Favorite, Furniture, Reservation, Sale, Supplier

# Valid 1x1 GIF so Pillow accepts it in the ImageField.
GIF_1PX = bytes.fromhex('47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b')


def photo():
    return SimpleUploadedFile('furniture.gif', GIF_1PX, content_type='image/gif')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class NordikaBackendTests(APITestCase):
    """Checks business rules, role-based security and critical edge cases on the REST endpoints."""
    def setUp(self):
        # Users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@nordika.com',
            password='testpassword123',
            first_name='Test',
            last_name='User'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # Supplier and category
        self.supplier = Supplier.objects.create(
            name='Nordic Workshop Test',
            contact_name='Hans',
            phone='12345678',
            email='hans@nordic.com'
        )
        self.category = Category.objects.create(
            name='Living Rooms Test',
            description='Category for living room tests'
        )

        # Furniture
        self.furniture = Furniture.objects.create(
            name='Nordic Test Sofa',
            description='Test sofa',
            price=Decimal('9999.00'),
            stock=10,
            category=self.category,
            supplier=self.supplier
        )

    # 1. AUTHENTICATION
    def test_login_success(self):
        self.client.credentials()  # No previous token
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
            'username': 'newuser',
            'email': 'new@nordika.com',
            'password': 'Furniture$Blue47',
            'password_confirm': 'Furniture$Blue47',
            'first_name': 'New',
            'last_name': 'Customer'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_rejects_weak_password(self):
        self.client.credentials()
        # Common, numbers only, similar to the username and too short
        for password in ['password123', '12345678', 'weakuser', 'Ab1!']:
            res = self.client.post('/api-register/', {
                'username': 'weakuser', 'email': 'weak@nordika.com', 'password': password,
            })
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, password)
            self.assertIn('password', res.data)
        self.assertFalse(User.objects.filter(username='weakuser').exists())

    def test_user_me_profile(self):
        response = self.client.get('/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')

        patch_response = self.client.patch('/me/', {'first_name': 'Updated'})
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['first_name'], 'Updated')

    def test_user_me_patch_invalid_email_format(self):
        # Invalid email format -> 400
        for invalid_email in ['hello', 'not-an-email', 'user@', '@domain.com', 'test@.com']:
            res = self.client.patch('/me/', {'email': invalid_email}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, f"Failed for: {invalid_email}")
            self.assertIn('email', res.data)

    def test_user_me_patch_email_non_text(self):
        # Non-text email (number, list, dict, null) -> 400 (never 500!)
        non_text_values = [
            12345,
            ['email@nordika.com'],
            {'email': 'nordika'},
            None,
        ]
        for val in non_text_values:
            res = self.client.patch('/me/', {'email': val}, format='json')
            self.assertNotEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR, f"500 received for {val}")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, f"Failed for: {val}")
            self.assertIn('email', res.data)

    def test_user_me_patch_duplicate_email(self):
        # Duplicate email -> 400
        User.objects.create_user(
            username='other_user',
            email='other@nordika.com',
            password='Furniture$Blue47'
        )
        # Trying to use another user's email
        res = self.client.patch('/me/', {'email': 'other@nordika.com'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', res.data)

        # Case-insensitive check
        res_upper = self.client.patch('/me/', {'email': 'OTHER@NORDIKA.COM'}, format='json')
        self.assertEqual(res_upper.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', res_upper.data)

    def test_change_password(self):
        res = self.client.post('/change-password/', {'current_password': 'wrong', 'new_password': 'newpass123'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        for weak in ['123', 'password123', '98765432']:
            res = self.client.post('/change-password/', {'current_password': 'testpassword123', 'new_password': weak}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, weak)
            self.assertTrue(res.data['detail'])

        res = self.client.post('/change-password/', {'current_password': 'testpassword123', 'new_password': 'newpass123'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotEqual(res.data['token'], self.token.key)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))
        # The old token no longer works
        self.assertEqual(self.client.get('/me/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_account(self):
        reservation = Reservation.objects.create(user=self.user, furniture=self.furniture, quantity=3)
        Furniture.objects.filter(pk=self.furniture.pk).update(stock=7)

        res = self.client.delete('/me/', {'password': 'wrong'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.get(pk=self.user.pk).is_active)

        res = self.client.delete('/me/', {'password': 'testpassword123'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.CANCELLED)
        # Staff sees the reservation flagged as belonging to a deleted account
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=User.objects.create_user(username='admin_del', password='x', is_staff=True)).key)
        res = self.client.get(f'/reservations/{reservation.pk}/')
        self.assertFalse(res.data['user_active'])
        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 10)

        self.client.credentials()
        res = self.client.post('/api-token-auth/', {'username': 'testuser', 'password': 'testpassword123'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Username and email are free for a new account
        res = self.client.post('/api-register/', {
            'username': 'testuser', 'email': 'test@nordika.com', 'password': 'another123',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_user_me_patch_empty_email(self):
        # Empty email -> 400
        for empty_val in ['', '   ']:
            res = self.client.patch('/me/', {'email': empty_val}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, f"Failed for: {repr(empty_val)}")
            self.assertIn('email', res.data)

    def test_user_me_patch_username_read_only(self):
        # Trying to change the username -> it does not change
        res = self.client.patch('/me/', {'username': 'new_username'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(res.data['username'], 'testuser')

    def test_user_me_patch_valid_update(self):
        # Valid update of first_name, last_name, email -> 200
        payload = {
            'first_name': 'UpdatedFirstName',
            'last_name': 'UpdatedLastName',
            'email': '  NEW_EMAIL@NORDIKA.COM  '
        }
        res = self.client.patch('/me/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'UpdatedFirstName')
        self.assertEqual(self.user.last_name, 'UpdatedLastName')
        # Normalized with strip().lower()
        self.assertEqual(self.user.email, 'new_email@nordika.com')

        self.assertEqual(res.data['first_name'], 'UpdatedFirstName')
        self.assertEqual(res.data['last_name'], 'UpdatedLastName')
        self.assertEqual(res.data['email'], 'new_email@nordika.com')
        self.assertEqual(res.data['username'], 'testuser')

        # Saving the user's own email again does not raise a duplicate error
        res_same_email = self.client.patch('/me/', {'email': 'new_email@nordika.com'}, format='json')
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

    # 2. MODELS AND RELATIONS & NESTED SERIALIZERS
    def test_furniture_nested_serializer(self):
        response = self.client.get(f'/furniture/{self.furniture.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('category', response.data)
        self.assertEqual(response.data['category']['name'], 'Living Rooms Test')
        self.assertIn('supplier', response.data)
        self.assertEqual(response.data['supplier']['name'], 'Nordic Workshop Test')
        self.assertIn('is_favorite', response.data)
        self.assertFalse(response.data['is_favorite'])

    # 3. SEARCH AND FILTERS
    def test_furniture_search_and_filter(self):
        response = self.client.get('/furniture/?search=Nordic')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

        # Category filter
        cat_response = self.client.get(f'/furniture/?category={self.category.id}')
        self.assertEqual(cat_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cat_response.data['count'], 1)

        # Price filter
        price_response = self.client.get('/furniture/?price_min=10000')
        self.assertEqual(price_response.status_code, status.HTTP_200_OK)
        self.assertEqual(price_response.data['count'], 0)

    # 4. CONFIGURABLE PAGINATION
    def test_configurable_pagination(self):
        response = self.client.get('/furniture/?page_size=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page_size'], 2)
        self.assertIn('results', response.data)
        self.assertIn('total_pages', response.data)

    def test_categories_and_suppliers_without_pagination(self):
        # More than 100 (the page_size maximum) to check that all of them arrive.
        Category.objects.bulk_create([Category(name=f'Cat {i:03}') for i in range(120)])
        Supplier.objects.bulk_create([Supplier(name=f'Sup {i:03}') for i in range(120)])
        for url, total in [('/categories/', Category.objects.count()), ('/suppliers/', Supplier.objects.count())]:
            response = self.client.get(f'{url}?page_size=10')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsInstance(response.data, list)
            self.assertEqual(len(response.data), total)
        # Search still works without pagination.
        response = self.client.get('/categories/?search=Cat 119')
        self.assertEqual([c['name'] for c in response.data], ['Cat 119'])

    # 5. VALIDATIONS
    def test_furniture_validation_negative_price(self):
        self._admin_client()
        response = self.client.post('/furniture/', {
            'name': 'Invalid Furniture',
            'description': 'Test',
            'price': '-50.00',
            'stock': 5,
            'supplier_id': self.supplier.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_furniture_validation_requires_photo_on_create(self):
        self._admin_client()
        response = self.client.post('/furniture/', {
            'name': 'Furniture Without Photo',
            'price': '100.00',
            'stock': 5,
            'supplier_id': self.supplier.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data)

    def test_furniture_validation_decimal_stock(self):
        self._admin_client()
        response = self.client.post('/furniture/', {
            'name': 'Decimal Stock Furniture',
            'price': '100.00',
            'stock': '2.5',
            'supplier_id': self.supplier.id,
            'image': photo(),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('stock', response.data)

    # 6. CUSTOM ACTIONS (Favorites)
    def test_toggle_favorite(self):
        # Toggle ON
        toggle_res = self.client.post(f'/furniture/{self.furniture.id}/toggle_favorite/')
        self.assertEqual(toggle_res.status_code, status.HTTP_200_OK)
        self.assertTrue(toggle_res.data['is_favorite'])
        self.assertTrue(Favorite.objects.filter(user=self.user, furniture=self.furniture).exists())

        # Check my_favorites
        my_favs = self.client.get('/furniture/my_favorites/')
        self.assertEqual(my_favs.status_code, status.HTTP_200_OK)
        self.assertEqual(my_favs.data['count'], 1)

        # Toggle OFF
        toggle_res2 = self.client.post(f'/furniture/{self.furniture.id}/toggle_favorite/')
        self.assertEqual(toggle_res2.status_code, status.HTTP_200_OK)
        self.assertFalse(toggle_res2.data['is_favorite'])

    def test_toggle_favorite_double_tap_does_not_500(self):
        # Simulates a double tap: the other request creates the favorite right after this one
        # checked whether it existed (exists() or delete()) and found nothing.
        already_created = []

        def other_request_creates_after(original_method):
            def wrapper(qs):
                result = original_method(qs)
                if qs.model is Favorite and not already_created:
                    already_created.append(True)
                    Favorite.objects.create(user=self.user, furniture=self.furniture)
                return result
            return wrapper

        with patch.object(QuerySet, 'exists', other_request_creates_after(QuerySet.exists)), \
                patch.object(QuerySet, 'delete', other_request_creates_after(QuerySet.delete)):
            res = self.client.post(f'/furniture/{self.furniture.id}/toggle_favorite/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['is_favorite'])
        self.assertEqual(Favorite.objects.filter(user=self.user, furniture=self.furniture).count(), 1)

    def test_get_requires_token(self):
        self.client.credentials()
        for url in ['/furniture/', '/furniture/featured/', '/categories/', '/suppliers/']:
            self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED, url)

    # 7. RESERVATIONS
    def _admin_client(self):
        admin, _ = User.objects.get_or_create(username='admin_test', defaults={'is_staff': True})
        if not admin.is_staff:
            admin.is_staff = True
            admin.save()
        token, _ = Token.objects.get_or_create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

    def _reserve(self, quantity):
        return self.client.post('/reservations/', {'furniture_id': self.furniture.id, 'quantity': quantity})

    def test_reservation_deducts_stock(self):
        res = self._reserve(3)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'PENDING')
        self.assertEqual(res.data['code'], f"APT-{res.data['id']}")
        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 7)

    def test_reservation_insufficient_stock(self):
        self.assertEqual(self._reserve(11).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._reserve(0).status_code, status.HTTP_400_BAD_REQUEST)
        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 10)

    def test_admin_cannot_reserve(self):
        self._admin_client()
        res = self._reserve(2)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Reservation.objects.exists())
        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 10)

    def test_admin_filters_everyones_active_and_history(self):
        pending_id = self._reserve(1).data['id']
        resolved_id = self._reserve(1).data['id']
        other = User.objects.create_user('other', password='x')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=other).key)
        other_pending_id = self._reserve(1).data['id']
        self._admin_client()
        self.client.post(f'/reservations/{resolved_id}/reject/')

        active = self.client.get('/reservations/', {'status': 'PENDING'}).data
        self.assertEqual({r['id'] for r in active['results']}, {pending_id, other_pending_id})
        history = self.client.get('/reservations/', {'history': 'true'}).data
        self.assertEqual([r['id'] for r in history['results']], [resolved_id])

    def test_user_cannot_accept_or_see_others(self):
        reservation_id = self._reserve(2).data['id']
        self.assertEqual(self.client.post(f'/reservations/{reservation_id}/accept/').status_code, status.HTTP_403_FORBIDDEN)
        other = User.objects.create_user('other', password='x')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=other).key)
        self.assertEqual(self.client.get(f'/reservations/{reservation_id}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_accept_records_sale(self):
        reservation_id = self._reserve(2).data['id']
        self._admin_client()
        res = self.client.post(f'/reservations/{reservation_id}/accept/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'ACCEPTED')
        sale = Sale.objects.get(reservation_id=reservation_id)
        self.assertEqual(sale.total, Decimal('19998.00'))
        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 8)
        # It cannot be resolved twice
        res = self.client.post(f'/reservations/{reservation_id}/reject/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['detail'], 'El apartado ya fue aceptado.')

    def test_reject_releases_stock(self):
        reservation_id = self._reserve(4).data['id']
        self._admin_client()
        res = self.client.post(f'/reservations/{reservation_id}/reject/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'REJECTED')
        self.assertFalse(Sale.objects.filter(reservation_id=reservation_id).exists())
        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 10)

    def test_reservation_expires_after_5_days(self):
        res = self._reserve(3)
        reservation_id = res.data['id']
        created = Reservation.objects.get(pk=reservation_id).created_at
        self.assertEqual(datetime.fromisoformat(res.data['expires_at']), created + timedelta(days=5))

        # Still valid: not cancelled
        Reservation.objects.filter(pk=reservation_id).update(created_at=timezone.now() - timedelta(days=4, hours=23))
        self.assertEqual(self.client.get(f'/reservations/{reservation_id}/').data['status'], 'PENDING')

        # Expired: cancelled and stock released
        Reservation.objects.filter(pk=reservation_id).update(created_at=timezone.now() - timedelta(days=5, minutes=1))
        res = self.client.get(f'/reservations/{reservation_id}/')
        self.assertEqual(res.data['status'], 'CANCELLED')
        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 10)

        # It can no longer be accepted
        self._admin_client()
        self.assertEqual(self.client.post(f'/reservations/{reservation_id}/accept/').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Sale.objects.filter(reservation_id=reservation_id).exists())

    def test_closing_reservation_twice_does_not_return_stock_twice(self):
        # Simulates two requests that read the same pending reservation before either closed it
        reservation_id = self._reserve(3).data['id']
        read_1 = Reservation.objects.get(pk=reservation_id)
        read_2 = Reservation.objects.get(pk=reservation_id)

        self.assertTrue(read_1.close(Reservation.CANCELLED))
        self.assertFalse(read_2.close(Reservation.REJECTED))
        self.assertFalse(read_2.close(Reservation.ACCEPTED))

        self.furniture.refresh_from_db()
        self.assertEqual(self.furniture.stock, 10)
        self.assertEqual(Reservation.objects.get(pk=reservation_id).status, Reservation.CANCELLED)
        self.assertFalse(Sale.objects.filter(reservation_id=reservation_id).exists())

    def test_furniture_releases_expired_stock(self):
        reservation_id = self._reserve(4).data['id']
        Reservation.objects.filter(pk=reservation_id).update(created_at=timezone.now() - timedelta(days=6))
        res = self.client.get(f'/furniture/{self.furniture.id}/')
        self.assertEqual(res.data['stock'], 10)

    # 8. DELETION WITH PROTECTED DEPENDENCIES (409 CONFLICT)
    def test_delete_supplier_with_furniture_returns_409(self):
        self._admin_client()
        # self.supplier has self.furniture linked (1 item)
        res = self.client.delete(f'/suppliers/{self.supplier.id}/')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data['detail'], 'No se puede eliminar: el proveedor tiene 1 mueble asociado.')
        self.assertTrue(Supplier.objects.filter(id=self.supplier.id).exists())

        # With more than one linked item (plural)
        Furniture.objects.create(
            name='Extra Furniture',
            price=Decimal('1500.00'),
            stock=2,
            category=self.category,
            supplier=self.supplier
        )
        res_plural = self.client.delete(f'/suppliers/{self.supplier.id}/')
        self.assertEqual(res_plural.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res_plural.data['detail'], 'No se puede eliminar: el proveedor tiene 2 muebles asociados.')

    def test_delete_supplier_without_furniture_returns_204(self):
        self._admin_client()
        empty_supplier = Supplier.objects.create(name='Supplier Without Furniture')
        res = self.client.delete(f'/suppliers/{empty_supplier.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Supplier.objects.filter(id=empty_supplier.id).exists())

    def test_delete_furniture_with_reservations_returns_409(self):
        self._reserve(2)
        self._admin_client()
        res = self.client.delete(f'/furniture/{self.furniture.id}/')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data['detail'], 'No se puede eliminar: el mueble tiene 1 apartado asociado.')
        self.assertTrue(Furniture.objects.filter(id=self.furniture.id).exists())

        # With more than one linked reservation (plural):
        # switch to the regular customer to reserve and back to admin
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self._reserve(1)
        self._admin_client()
        res_plural = self.client.delete(f'/furniture/{self.furniture.id}/')
        self.assertEqual(res_plural.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res_plural.data['detail'], 'No se puede eliminar: el mueble tiene 2 apartados asociados.')

    def test_delete_furniture_without_reservations_returns_204(self):
        self._admin_client()
        unreserved = Furniture.objects.create(
            name='Unreserved Furniture',
            price=Decimal('500.00'),
            stock=5,
            category=self.category,
            supplier=self.supplier
        )
        res = self.client.delete(f'/furniture/{unreserved.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Furniture.objects.filter(id=unreserved.id).exists())

    def test_delete_furniture_with_rejected_reservation_returns_204(self):
        reservation_id = self._reserve(2).data['id']
        self._admin_client()
        self.client.post(f'/reservations/{reservation_id}/reject/')
        res = self.client.delete(f'/furniture/{self.furniture.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Furniture.objects.filter(id=self.furniture.id).exists())

    def test_delete_furniture_with_cancelled_reservation_returns_204(self):
        reservation_id = self._reserve(1).data['id']
        Reservation.objects.filter(id=reservation_id).update(status=Reservation.CANCELLED)
        self._admin_client()
        res = self.client.delete(f'/furniture/{self.furniture.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Furniture.objects.filter(id=self.furniture.id).exists())

    def test_delete_furniture_with_accepted_reservation_returns_409(self):
        reservation_id = self._reserve(1).data['id']
        self._admin_client()
        self.client.post(f'/reservations/{reservation_id}/accept/')
        res = self.client.delete(f'/furniture/{self.furniture.id}/')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data['detail'], 'No se puede eliminar: el mueble tiene 1 apartado asociado.')
        self.assertTrue(Furniture.objects.filter(id=self.furniture.id).exists())

    # 9. CRUD PERMISSIONS: ONLY STAFF CAN CREATE/EDIT/DELETE
    def test_non_staff_user_gets_403_on_supplier_category_furniture_crud(self):
        # Regular authenticated user (not staff)
        # Suppliers
        self.assertEqual(self.client.post('/suppliers/', {'name': 'New Supplier'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f'/suppliers/{self.supplier.id}/', {'name': 'Edit'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/suppliers/{self.supplier.id}/').status_code, status.HTTP_403_FORBIDDEN)

        # Categories
        self.assertEqual(self.client.post('/categories/', {'name': 'New Category'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f'/categories/{self.category.id}/', {'name': 'Edit'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/categories/{self.category.id}/').status_code, status.HTTP_403_FORBIDDEN)

        # Furniture
        furniture_payload = {
            'name': 'New Furniture',
            'price': '1200.00',
            'stock': 3,
            'supplier_id': self.supplier.id,
        }
        self.assertEqual(self.client.post('/furniture/', furniture_payload).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f'/furniture/{self.furniture.id}/', {'name': 'Edit'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/furniture/{self.furniture.id}/').status_code, status.HTTP_403_FORBIDDEN)

        # But they CAN read them (safe GET methods)
        self.assertEqual(self.client.get('/suppliers/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/categories/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/furniture/').status_code, status.HTTP_200_OK)

        # And they can use the customer actions on furniture
        self.assertEqual(self.client.post(f'/furniture/{self.furniture.id}/toggle_favorite/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/furniture/my_favorites/').status_code, status.HTTP_200_OK)

    def test_staff_user_can_crud_supplier_category_furniture(self):
        self._admin_client()

        # Supplier
        sup_res = self.client.post('/suppliers/', {'name': 'Admin Supplier'})
        self.assertEqual(sup_res.status_code, status.HTTP_201_CREATED)
        sup_id = sup_res.data['id']
        patch_sup = self.client.patch(f'/suppliers/{sup_id}/', {'name': 'Admin Supplier Edit'})
        self.assertEqual(patch_sup.status_code, status.HTTP_200_OK)
        del_sup = self.client.delete(f'/suppliers/{sup_id}/')
        self.assertEqual(del_sup.status_code, status.HTTP_204_NO_CONTENT)

        # Category
        cat_res = self.client.post('/categories/', {'name': 'Admin Category'})
        self.assertEqual(cat_res.status_code, status.HTTP_201_CREATED)
        cat_id = cat_res.data['id']
        patch_cat = self.client.patch(f'/categories/{cat_id}/', {'name': 'Admin Category Edit'})
        self.assertEqual(patch_cat.status_code, status.HTTP_200_OK)
        del_cat = self.client.delete(f'/categories/{cat_id}/')
        self.assertEqual(del_cat.status_code, status.HTTP_204_NO_CONTENT)

        # Furniture
        furniture_res = self.client.post('/furniture/', {
            'name': 'Furniture Created By Staff',
            'description': 'Staff description',
            'price': '2500.00',
            'stock': 4,
            'supplier_id': self.supplier.id,
            'category_id': self.category.id,
            'image': photo(),
        })
        self.assertEqual(furniture_res.status_code, status.HTTP_201_CREATED)
        furniture_id = furniture_res.data['id']
        patch_furniture = self.client.patch(f'/furniture/{furniture_id}/', {'name': 'Furniture Edited By Staff'})
        self.assertEqual(patch_furniture.status_code, status.HTTP_200_OK)
        del_furniture = self.client.delete(f'/furniture/{furniture_id}/')
        self.assertEqual(del_furniture.status_code, status.HTTP_204_NO_CONTENT)

    # 10. RESERVATION CONTACT DATA & CUSTOMER CREATION BY ADMIN
    def test_reservation_serializer_includes_user_contact(self):
        self.user.first_name = 'Juan'
        self.user.last_name = 'Perez'
        self.user.email = 'juan.perez@nordika.com'
        self.user.save()

        res = self._reserve(1)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['user_username'], self.user.username)
        self.assertEqual(res.data['user_email'], 'juan.perez@nordika.com')
        self.assertEqual(res.data['user_full_name'], 'Juan Perez')

    def test_admin_creates_customer_successfully(self):
        self._admin_client()
        payload = {
            'username': 'new_customer',
            'email': 'new_customer@nordika.com',
            'password': 'Furniture$Blue47',
            'password_confirm': 'Furniture$Blue47',
            'first_name': 'Customer',
            'last_name': 'Test'
        }
        res = self.client.post('/users/create_customer/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['username'], 'new_customer')
        self.assertEqual(res.data['email'], 'new_customer@nordika.com')
        self.assertEqual(res.data['first_name'], 'Customer')
        self.assertEqual(res.data['last_name'], 'Test')
        self.assertFalse(res.data['is_staff'])

        created = User.objects.get(username='new_customer')
        self.assertFalse(created.is_staff)
        self.assertTrue(created.check_password('Furniture$Blue47'))

    def test_create_customer_non_admin_gets_403(self):
        payload = {
            'username': 'customer_no_auth',
            'email': 'noauth@nordika.com',
            'password': 'Furniture$Blue47',
        }
        res = self.client.post('/users/create_customer/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_customer_validations(self):
        self._admin_client()
        # Passwords do not match
        res1 = self.client.post('/users/create_customer/', {
            'username': 'user1',
            'email': 'u1@nordika.com',
            'password': 'Furniture$Blue47',
            'password_confirm': 'different',
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Duplicate email
        res2 = self.client.post('/users/create_customer/', {
            'username': 'user2',
            'email': self.user.email,
            'password': 'Furniture$Blue47',
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_customer_api_prefix_route(self):
        self._admin_client()
        res_api = self.client.post('/api/users/create_customer/', {
            'username': 'customer_api_prefix',
            'email': 'api_prefix@nordika.com',
            'password': 'Furniture$Blue47',
        }, format='json')
        self.assertEqual(res_api.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='customer_api_prefix').exists())
