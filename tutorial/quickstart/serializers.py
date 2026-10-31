from decimal import Decimal
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from .models import Proveedor, Categoria, Mueble, Favorito, MovimientoInventario


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'is_staff', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6, required=True)
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


class CategoriaSerializer(serializers.ModelSerializer):
    muebles_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'descripcion', 'muebles_count']

    def get_muebles_count(self, obj):
        return obj.muebles.count()


class ProveedorSerializer(serializers.ModelSerializer):
    muebles_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Proveedor
        fields = ['id', 'nombre', 'contacto', 'telefono', 'email', 'creado_en', 'muebles_count']

    def get_muebles_count(self, obj):
        return obj.muebles.count()


class MuebleNestedCategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'descripcion']


class MuebleNestedProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = ['id', 'nombre', 'contacto', 'telefono', 'email']


class MuebleSerializer(serializers.ModelSerializer):
    categoria = MuebleNestedCategoriaSerializer(read_only=True)
    proveedor = MuebleNestedProveedorSerializer(read_only=True)

    categoria_id = serializers.PrimaryKeyRelatedField(
        queryset=Categoria.objects.all(),
        source='categoria',
        write_only=True,
        required=False,
        allow_null=True
    )
    proveedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Proveedor.objects.all(),
        source='proveedor',
        write_only=True,
        required=True
    )

    is_favorito = serializers.SerializerMethodField(read_only=True)
    favoritos_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Mueble
        fields = [
            'id',
            'nombre',
            'descripcion',
            'precio',
            'stock',
            'imagen',
            'categoria',
            'proveedor',
            'categoria_id',
            'proveedor_id',
            'is_favorito',
            'favoritos_count',
            'creado_en',
            'actualizado_en',
        ]
        read_only_fields = ['id', 'creado_en', 'actualizado_en']

    def get_is_favorito(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            return Favorito.objects.filter(usuario=request.user, mueble=obj).exists()
        return False

    def get_favoritos_count(self, obj):
        return obj.favoritos.count()

    def validate_precio(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("El precio debe ser mayor que 0.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock no puede ser negativo.")
        return value

    def validate_nombre(self, value):
        val = value.strip()
        if len(val) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return val


class FavoritoSerializer(serializers.ModelSerializer):
    mueble = MuebleSerializer(read_only=True)
    mueble_id = serializers.PrimaryKeyRelatedField(
        queryset=Mueble.objects.all(),
        source='mueble',
        write_only=True
    )

    class Meta:
        model = Favorito
        fields = ['id', 'usuario', 'mueble', 'mueble_id', 'fecha_agregado']
        read_only_fields = ['id', 'usuario', 'fecha_agregado']

    def validate(self, attrs):
        user = self.context['request'].user
        mueble = attrs.get('mueble')
        if Favorito.objects.filter(usuario=user, mueble=mueble).exists():
            raise serializers.ValidationError("Este mueble ya se encuentra en tus favoritos.")
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['usuario'] = user
        return super().create(validated_data)


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    mueble = MuebleSerializer(read_only=True)
    mueble_id = serializers.PrimaryKeyRelatedField(
        queryset=Mueble.objects.all(),
        source='mueble',
        write_only=True
    )
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = MovimientoInventario
        fields = [
            'id',
            'mueble',
            'mueble_id',
            'tipo_movimiento',
            'cantidad',
            'motivo',
            'usuario',
            'usuario_username',
            'fecha_movimiento',
        ]
        read_only_fields = ['id', 'usuario', 'fecha_movimiento']

    def validate(self, attrs):
        mueble = attrs.get('mueble')
        tipo = attrs.get('tipo_movimiento')
        cantidad = attrs.get('cantidad')

        if cantidad <= 0:
            raise serializers.ValidationError({'cantidad': "La cantidad debe ser mayor que 0."})

        if tipo == 'SALIDA' and mueble.stock < cantidad:
            raise serializers.ValidationError({
                'cantidad': f"Stock insuficiente. El stock actual es de {mueble.stock} unidades."
            })
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['usuario'] = request.user

        mueble = validated_data['mueble']
        tipo = validated_data['tipo_movimiento']
        cantidad = validated_data['cantidad']

        if tipo == 'ENTRADA':
            mueble.stock += cantidad
        elif tipo == 'SALIDA':
            mueble.stock -= cantidad
        elif tipo == 'AJUSTE':
            mueble.stock = cantidad
        mueble.save()

        return super().create(validated_data)
