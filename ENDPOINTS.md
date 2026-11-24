# Endpoints de la API Nordika

Todas las rutas responden igual en la raíz (`/muebles/`) y con prefijo `/api/` (`/api/muebles/`). En los ejemplos se usa `{{base_url}}` = `http://localhost:8000`.

## Autenticación en Postman

Casi todos los endpoints piden token. Después del login agrega este header:

```
Authorization: Token <token>
Content-Type: application/json
```

Para no copiarlo a mano, en la pestaña **Tests** del request de login pon `pm.environment.set("token", pm.response.json().token)` y usa `Token {{token}}` en el header.

**Permisos:** 🌐 público · 🔑 cualquier usuario con sesión · 👑 solo admin (`is_staff`)

---

## 1. Autenticación y cuenta

| Método | Ruta | Permiso |
|---|---|---|
| POST | `/api-token-auth/` | 🌐 |
| POST | `/api-register/` | 🌐 |
| POST | `/users/crear_cliente/` | 👑 |
| GET / PATCH / DELETE | `/me/` | 🔑 |
| POST | `/change-password/` | 🔑 |
| POST | `/logout/` | 🔑 |
| POST | `/reset-token/` | 🔑 |

**POST `/api-token-auth/`** (login)
```json
{
  "username": "admin",
  "password": "tu_password"
}
```

**POST `/api-register/`** (`password_confirm` es opcional; la contraseña tiene que pasar los validadores de Django)
```json
{
  "username": "cliente_prueba",
  "email": "cliente@prueba.com",
  "password": "Nordika2026!Segura",
  "password_confirm": "Nordika2026!Segura",
  "first_name": "Juan",
  "last_name": "Pérez"
}
```

**POST `/users/crear_cliente/`** 👑: mismo body que el registro. Siempre crea al usuario con `is_staff=false`.
```json
{
  "username": "cliente_admin",
  "email": "cliente2@prueba.com",
  "password": "Nordika2026!Segura",
  "password_confirm": "Nordika2026!Segura",
  "first_name": "Ana",
  "last_name": "López"
}
```

**GET `/me/`**: sin body.

**PATCH `/me/`**: solo se pueden editar `email`, `first_name` y `last_name`. `username` no se puede cambiar.
```json
{
  "first_name": "Juan Carlos",
  "last_name": "Pérez",
  "email": "nuevo@prueba.com"
}
```

**DELETE `/me/`**: desactiva la cuenta, borra el token y cancela los apartados pendientes. Responde 204, o 400 si la contraseña es incorrecta.
```json
{
  "password": "Nordika2026!Segura"
}
```

**POST `/change-password/`**: devuelve un token nuevo y el anterior deja de servir.
```json
{
  "current_password": "Nordika2026!Segura",
  "new_password": "OtraClave2026!Fuerte"
}
```

**POST `/logout/`** y **POST `/reset-token/`**: sin body. `reset-token` devuelve un token nuevo.

---

## 2. Categorías: `/categorias/`
🔑 para leer, 👑 para escribir. No tiene paginación.

| Método | Ruta |
|---|---|
| GET | `/categorias/?search=sala&ordering=nombre` |
| GET | `/categorias/{id}/` |
| POST | `/categorias/` |
| PUT / PATCH | `/categorias/{id}/` |
| DELETE | `/categorias/{id}/` |

**POST / PUT**
```json
{
  "nombre": "Salas",
  "descripcion": "Sofás, sillones y mesas de centro"
}
```

---

## 3. Proveedores: `/proveedores/`
🔑 para leer, 👑 para escribir. No tiene paginación. Un DELETE devuelve **409** si el proveedor todavía tiene muebles.

| Método | Ruta |
|---|---|
| GET | `/proveedores/?search=madera&ordering=-creado_en` |
| GET | `/proveedores/{id}/` |
| POST | `/proveedores/` |
| PUT / PATCH | `/proveedores/{id}/` |
| DELETE | `/proveedores/{id}/` |

**POST / PUT** (`nombre` es único; los demás campos son opcionales)
```json
{
  "nombre": "Maderas del Norte",
  "contacto": "Luis Ramírez",
  "telefono": "6141234567",
  "email": "ventas@maderasnorte.com"
}
```

---

## 4. Muebles: `/muebles/`
🔑 para leer, 👑 para escribir. Tiene paginación.

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/muebles/` | 🔑 |
| GET | `/muebles/{id}/` | 🔑 |
| POST | `/muebles/` | 👑 |
| PUT / PATCH | `/muebles/{id}/` | 👑 |
| DELETE | `/muebles/{id}/` | 👑 (409 si tiene apartados pendientes, aceptados o con venta) |
| POST | `/muebles/{id}/toggle_favorito/` | 🔑, sin body |
| GET | `/muebles/mis_favoritos/` | 🔑 |
| GET | `/muebles/destacados/` | 🔑 (6 muebles, sin paginación) |

**Query params de GET `/muebles/`:**
```
?search=sofa
&categoria=1
&categoria_nombre=sala
&proveedor=2
&precio_min=1000
&precio_max=15000
&en_stock=true
&ordering=-precio        (precio, stock, creado_en, nombre)
&page=1
&page_size=20            (máx. 100)
```

⚠️ **POST `/muebles/` necesita `form-data`, no JSON**, porque `imagen` es obligatoria al crear. En Postman: Body → form-data.

| Key | Tipo | Valor |
|---|---|---|
| nombre | Text | Sofá Nórdico |
| descripcion | Text | Sofá de 3 plazas en lino gris |
| precio | Text | 12999.90 |
| stock | Text | 5 |
| categoria_id | Text | 1 |
| proveedor_id | Text | 1 |
| imagen | **File** | (selecciona un .jpg/.png) |

**PATCH `/muebles/{id}/`**: en la edición la imagen no es obligatoria, así que aquí sí puedes mandar JSON.
```json
{
  "precio": "11499.00",
  "stock": 8,
  "categoria_id": 2
}
```

Para un **PUT** con JSON tienes que mandar todos los campos requeridos: `nombre`, `precio`, `stock` y `proveedor_id`.

---

## 5. Favoritos: `/favoritos/`
🔑. Un cliente solo ve sus propios favoritos; el admin ve todos.

| Método | Ruta |
|---|---|
| GET | `/favoritos/?page=1&page_size=10` |
| GET | `/favoritos/{id}/` |
| POST | `/favoritos/` |
| DELETE | `/favoritos/{id}/` |

**POST** (devuelve 400 si el mueble ya está en favoritos)
```json
{
  "mueble_id": 1
}
```

---

## 6. Apartados: `/apartados/`
🔑. No existen PUT, PATCH ni DELETE.

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/apartados/` | 🔑 (un cliente ve solo los suyos) |
| GET | `/apartados/{id}/` | 🔑 |
| POST | `/apartados/` | 🔑 **solo clientes** (un admin recibe 403) |
| POST | `/apartados/{id}/aceptar/` | 👑, sin body (crea la Venta) |
| POST | `/apartados/{id}/rechazar/` | 👑, sin body (devuelve el stock) |

**Query params de GET:**
```
?estado=PENDIENTE              (PENDIENTE, ACEPTADO, RECHAZADO, CANCELADO)
&estado__in=ACEPTADO,RECHAZADO
&historial=true                (true = resueltos, false = pendientes)
&mueble=1
&search=sofa
&ordering=-creado_en           (creado_en, cantidad)
```

**POST** (descuenta el stock; devuelve 400 si no alcanza)
```json
{
  "mueble_id": 1,
  "cantidad": 2
}
```

---

## Flujo sugerido para probar
1. Login como admin y guarda el token.
2. Crea una categoría, luego un proveedor y luego un mueble (form-data).
3. Registra un cliente con `/api-register/` y guarda su token.
4. Con el token del cliente: crea un apartado y prueba `toggle_favorito`.
5. Con el token del admin: llama a `/apartados/{id}/aceptar/` o a `/rechazar/`.

También están `/admin/` (panel de Django) y `/api-auth/login/` (login del navegador de DRF), pero no se necesitan en Postman.
