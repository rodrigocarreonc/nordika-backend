# Nordika Backend

Backend del proyecto **Nordika**, desarrollado con Django y Django REST Framework.

## Tecnologías

- Python
- Django
- Django REST Framework
- SQLite (base de datos local predeterminada de Django)

## Requisitos previos

Antes de comenzar, instala:

- [Python](https://www.python.org/downloads/) — una versión compatible con las dependencias del proyecto.
- [Git](https://git-scm.com/downloads).

## Instalación y configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/rodrigocarreonc/nordika-backend.git
cd nordika-backend
```
### 2. Crear el entorno virtual

En Windows:

```powershell
python -m venv .venv
```

### 3. Activar el entorno virtual

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Si utilizas CMD:

```cmd
.venv\Scripts\activate.bat
```

### 4. Instalar las dependencias

Con el entorno virtual activado:

```bash
python -m pip install -r requirements.txt
```

### 5. Aplicar las migraciones

```bash
python manage.py migrate
```

Este comando prepara la base de datos local de Django.

### 6. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

Abre en tu navegador:

http://127.0.0.1:8000/

Para detener el servidor, presiona `Ctrl + C` en la terminal.

## Flujo de trabajo en equipo

1. Obtén los últimos cambios antes de comenzar a trabajar:

   ```bash
   git pull
   ```

2. Crea una rama para tu tarea:

   ```bash
   git switch -c feat/nombre-de-la-tarea
   ```

3. Realiza tus cambios y revisa qué archivos modificaste:

   ```bash
   git status
   git diff
   ```

4. Guarda tus cambios en un commit:

   ```bash
   git add .
   git commit -m "Describe el cambio realizado"
   ```
   Utilizar la convención de *"Conventional Commit*.

   *'type[optional scope]: :icon: description'*
   [Icons para *Conventional Commit*](https://gist.github.com/parmentf/035de27d6ed1dce0b36a)


5. Sube tu rama a GitHub:

   ```bash
   git push -u origin feat/nombre-de-la-tarea
   ```

6. Abre un Pull Request para revisar e integrar los cambios en la rama principal, siguiendo los acuerdos del equipo.

## Consideraciones

- No subir el entorno virtual `.venv/` al repositorio.
- No subir contraseñas, claves API ni archivos `.env` con información sensible.
- Si se agrega una dependencia, actualizar `requirements.txt` y compartir el cambio.
- No subir la base de datos local `db.sqlite3`, salvo que el equipo acuerde expresamente otra estrategia.
- Coordinar los cambios en modelos y migraciones para evitar conflictos.
