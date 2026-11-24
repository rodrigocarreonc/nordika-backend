"""DRF serializers for validation, response shape and atomic write operations."""

from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from .models import Category, Favorite, Furniture, Reservation, Sale, Supplier


def validate_password_rules(password, user):
    """Applies AUTH_PASSWORD_VALIDATORS and converts Django errors to the DRF format."""
    try:
        validate_password(password, user)
    except DjangoValidationError as e:
        raise serializers.ValidationError({'password': list(e.messages)})


class UserSerializer(serializers.ModelSerializer):
    """Basic user representation with administrative fields protected as read-only."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'is_staff', 'date_joined']


class UserProfileSerializer(serializers.ModelSerializer):
    """Own-profile editing (`/me/`): blocks changing username or privileges and requires a unique email."""
    email = serializers.EmailField(required=False, allow_blank=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined']
        read_only_fields = ['id', 'username', 'is_staff', 'date_joined']

    # Lowercases the email and excludes the user itself so saving without changes is allowed.
    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('El correo electrónico no puede estar vacío.')
        value = value.strip().lower()
        query = User.objects.filter(email__iexact=value)
        if self.instance and self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError('Este correo ya está en uso.')
        return value


class RegisterSerializer(serializers.ModelSerializer):
    """Public customer sign-up: validates uniqueness and password strength, and creates the token."""
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
        read_only_fields = ['id']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return value.lower()

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está en uso.")
        return value

    def validate(self, attrs):
        password_confirm = attrs.get('password_confirm')
        if password_confirm and attrs['password'] != password_confirm:
            raise serializers.ValidationError({'password_confirm': "Las contraseñas no coinciden."})
        # Unsaved user: only so the validator can compare the password against the user's data
        validate_password_rules(attrs['password'], User(**{k: attrs.get(k, '') for k in ('username', 'email', 'first_name', 'last_name')}))
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        Token.objects.get_or_create(user=user)
        return user


class CustomerCreateSerializer(serializers.ModelSerializer):
    """Customer creation from the admin panel: trims text and forces is_staff=False to prevent escalation."""
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
        read_only_fields = ['id']

    def validate_email(self, value):
        val = value.strip().lower()
        if not val:
            raise serializers.ValidationError("El correo electrónico no puede estar vacío.")
        if User.objects.filter(email__iexact=val).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return val

    def validate_username(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("El nombre de usuario no puede estar vacío.")
        if User.objects.filter(username__iexact=val).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está en uso.")
        return val

    def validate_first_name(self, value):
        return value.strip() if value else ''

    def validate_last_name(self, value):
        return value.strip() if value else ''

    def validate(self, attrs):
        password_confirm = attrs.get('password_confirm')
        if password_confirm and attrs.get('password') != password_confirm:
            raise serializers.ValidationError({'password_confirm': "Las contraseñas no coinciden."})
        # Unsaved user: only so the validator can compare the password against the user's data
        validate_password_rules(attrs['password'], User(**{k: attrs.get(k, '') for k in ('username', 'email', 'first_name', 'last_name')}))
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_staff=False,
            is_superuser=False
        )
        Token.objects.get_or_create(user=user)
        return user


class CategorySerializer(serializers.ModelSerializer):
    """Includes the furniture count to show it in the admin panel and filters."""
    furniture_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'furniture_count']

    def get_furniture_count(self, obj):
        return obj.furniture.count()


class SupplierSerializer(serializers.ModelSerializer):
    """Includes furniture_count to warn the admin when a supplier has linked items."""
    furniture_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact_name', 'phone', 'email', 'created_at', 'furniture_count']

    def get_furniture_count(self, obj):
        return obj.furniture.count()


# Reduced serializers to embed category and supplier inside Furniture without extra queries.
class FurnitureNestedCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class FurnitureNestedSupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact_name', 'phone', 'email']


class FurnitureSerializer(serializers.ModelSerializer):
    """Returns nested category/supplier on read, but accepts category_id/supplier_id on write.

    This split keeps the app's multipart forms simple without losing UI-ready data.
    """
    category = FurnitureNestedCategorySerializer(read_only=True)
    supplier = FurnitureNestedSupplierSerializer(read_only=True)

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True,
        required=False,
        allow_null=True
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        source='supplier',
        write_only=True,
        required=True
    )

    is_favorite = serializers.SerializerMethodField(read_only=True)
    favorites_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Furniture
        fields = [
            'id',
            'name',
            'description',
            'price',
            'stock',
            'image',
            'category',
            'supplier',
            'category_id',
            'supplier_id',
            'is_favorite',
            'favorites_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            return Favorite.objects.filter(user=request.user, furniture=obj).exists()
        return False

    def get_favorites_count(self, obj):
        return obj.favorites.count()

    def validate_price(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("El precio debe ser mayor que 0.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock no puede ser negativo.")
        return value

    def validate(self, attrs):
        # Only on create: editing keeps the photo it already has.
        if self.instance is None and not attrs.get('image'):
            raise serializers.ValidationError({'image': "La foto del mueble es obligatoria."})
        return attrs

    def validate_name(self, value):
        val = value.strip()
        if len(val) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return val


class FavoriteSerializer(serializers.ModelSerializer):
    """Always ties the favorite to the authenticated user and avoids duplicates per furniture."""
    furniture = FurnitureSerializer(read_only=True)
    furniture_id = serializers.PrimaryKeyRelatedField(
        queryset=Furniture.objects.all(),
        source='furniture',
        write_only=True
    )

    class Meta:
        model = Favorite
        fields = ['id', 'user', 'furniture', 'furniture_id', 'added_at']
        read_only_fields = ['id', 'user', 'added_at']

    def validate(self, attrs):
        user = self.context['request'].user
        furniture = attrs.get('furniture')
        if Favorite.objects.filter(user=user, furniture=furniture).exists():
            raise serializers.ValidationError("Este mueble ya se encuentra en tus favoritos.")
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SaleSerializer(serializers.ModelSerializer):
    """Embedded sale summary once a reservation has been accepted."""
    class Meta:
        model = Sale
        fields = ['id', 'unit_price', 'total', 'sold_at']


class ReservationSerializer(serializers.ModelSerializer):
    """Exposes customer contact data to staff and atomically deducts stock on create."""
    furniture = FurnitureSerializer(read_only=True)
    furniture_id = serializers.PrimaryKeyRelatedField(
        queryset=Furniture.objects.all(),
        source='furniture',
        write_only=True
    )
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.SerializerMethodField(read_only=True)
    user_active = serializers.BooleanField(source='user.is_active', read_only=True)
    code = serializers.ReadOnlyField()
    expires_at = serializers.DateTimeField(read_only=True)
    sale = SaleSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'code', 'user', 'user_username', 'user_email', 'user_full_name',
            'user_active', 'furniture', 'furniture_id', 'quantity', 'status', 'sale', 'expires_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'status', 'created_at', 'updated_at']

    def get_user_full_name(self, obj):
        if not obj.user:
            return ""
        first = (obj.user.first_name or "").strip()
        last = (obj.user.last_name or "").strip()
        return f"{first} {last}".strip()

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("La cantidad debe ser mayor que 0.")
        return value

    def create(self, validated_data):
        furniture = validated_data['furniture']
        quantity = validated_data['quantity']
        with transaction.atomic():
            # Conditional decrement in a single query: prevents over-reserving with concurrent requests.
            updated = Furniture.objects.filter(pk=furniture.pk, stock__gte=quantity).update(stock=F('stock') - quantity)
            if not updated:
                furniture.refresh_from_db()
                raise serializers.ValidationError({
                    'quantity': f"Stock insuficiente. El stock actual es de {furniture.stock} unidades."
                })
            validated_data['user'] = self.context['request'].user
            reservation = super().create(validated_data)
        reservation.furniture.refresh_from_db()
        return reservation
