# SharePoint to Dropbox Team Migrator

Este script automatiza la migración de archivos y carpetas desde una librería de SharePoint a la cuenta de Dropbox Business (Team) de un usuario específico, usando impersonación (as_user).

# Caracteristicas
-	Extraer archivos de SharePoint
-	Migrar archivos a Dropbox(Tabien a carpetas de miembros)
-	Registrar eventos
-	múltiples transferencias en paralelo
-	carga en sesiones (chunked upload) para archivos que superen cierto tamaño(150MB)( según las recomendaciones de Dropbox)
-	rate limiting (2 llamadas por segundo)

---

## Requisitos
- Crear un Token de Acceso para Dropbox: https://www.dropbox.com/developers/apps/info/v1h92z3n7kcgbtj#settings
- Crear App en Azure creando un client secreto dadno permisos a SharePoint
- Registra tu app en SharePoint: https://xxxx.sharepoint.com/_layouts/15/appregnew.aspx

- Python 3.7+ instalado
- Acceso de administrador a la consola de **SharePoint** y **Dropbox Business Team App**
- Permisos configurados en tu App de Dropbox:
  - **team_info.read**
  - **team_members.read**
  - **team_data.member_content.read**
  - **account_info.read**  _(para validar conexión, opcional si no llamas users_get_current_account)_
  - Scopes de archivos (files.metadata.read, files.content.read)

---

## Estructura de archivos

- `sharepoint_to_dropbox_team.py`  
  Script principal que:
  1. Conecta a SharePoint
  2. Conecta a Dropbox Team
  3. Impersona al usuario por email
  4. Recorre recursivamente carpetas y archivos en SharePoint
  5. Sube cada archivo a Dropbox con carga directa o sesión (chunked)

- `.env`  
  Variables de entorno necesarias (ver siguiente sección).

- `migration.log`  
  Archivo de log donde se registran info y errores de la migración.

---

## Variables de entorno (.env)
Crea un archivo `.env` en la misma carpeta con estas claves:

```dotenv
# SharePoint
SHAREPOINT_CLIENT_ID=tu_client_id
SHAREPOINT_CLIENT_SECRET=tu_client_secret
SHAREPOINT_SITE_URL=https://tuempresa.sharepoint.com/sites/NombreSitio
SHAREPOINT_FOLDER=/sites/NombreSitio/Shared Documents/Ruta/CarpetaOrigen

# Dropbox Team
DROPBOX_APP_KEY=tu_app_key_de_Dropbox
DROPBOX_APP_SECRET=tu_app_secret_de_Dropbox
DROPBOX_REFRESH_TOKEN=tu_refresh_token_offline_de_equipo
DROPBOX_MEMBER_EMAIL=email_del_miembro@tuempresa.com
DROPBOX_FOLDER=/Ruta/CarpetaDestino
```

- `SHAREPOINT_FOLDER`: ruta server-relative de la carpeta origen en SharePoint.
- `DROPBOX_FOLDER`: ruta destino en la cuenta Dropbox del miembro (por ejemplo, `/Migracion_Documentos`).

> **Nota**: No es necesario definir `DROPBOX_TEAM_MEMBER_ID`; el script buscará el ID a partir del email.

---

## Uso

1. **Prepara el entorno**:
   ```bash
   git clone <repo-url>
   cd <repo-folder>
   python -m venv venv
   source venv/bin/activate      # macOS/Linux
   venv\Scripts\activate       # Windows
   pip install -r requirements.txt
   ```

2. **Configura** `.env` con tus credenciales y rutas.
3. **Ejecuta** el script:
   ```bash
   python sharepoint_to_dropbox_team.py
   ```
4. **Verifica** la migración:
   - Revisa `migration.log` para ver detalles.
   - Entra a la cuenta de Dropbox del miembro y confirma que los archivos estén en `DROPBOX_FOLDER`.

---

## Ajustes adicionales

- **Rate limit**: por defecto 2 llamadas/s a Dropbox; modifica el valor en `@rate_limited(2)`.
- **Paralelismo**: usa `max_workers` en `ThreadPoolExecutor` para ajustar concurrencia.
- **Logging**: cambia nivel (`DEBUG`, `WARNING`) o formato en la configuración de `logging.basicConfig`.

---


