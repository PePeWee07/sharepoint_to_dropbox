import os
import sys
import io
import time
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from tqdm import tqdm

from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File

from dropbox import DropboxTeam
from dropbox.files import WriteMode, UploadSessionCursor, CommitInfo, FileMetadata, FolderMetadata


def rate_limited(max_per_second):
    """Decorador para limitar la cantidad de llamadas a la función."""
    min_interval = 1.0 / float(max_per_second)
    def decorator(func):
        last_call = [0.0]
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.perf_counter() - last_call[0]
            sleep_time = min_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            result = func(*args, **kwargs)
            last_call[0] = time.perf_counter()
            return result
        return wrapper
    return decorator

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class SharePointToDropboxMigrator:
    """Clase para migrar archivos desde SharePoint a Dropbox Business (Team) por usuario."""
    def __init__(self):
        load_dotenv()
        self.setup_sharepoint()
        self.setup_dropbox()

    def setup_sharepoint(self):
        """Configura la conexión con SharePoint"""
        client_id     = os.getenv('SHAREPOINT_CLIENT_ID')
        client_secret = os.getenv('SHAREPOINT_CLIENT_SECRET')
        site_url      = os.getenv('SHAREPOINT_SITE_URL')
        if not all([client_id, client_secret, site_url]):
            raise ValueError("Faltan credenciales de SharePoint en el archivo .env")
        credentials = ClientCredential(client_id, client_secret)
        self.ctx = ClientContext(site_url).with_credentials(credentials)
        web = self.ctx.web
        self.ctx.load(web)
        self.ctx.execute_query()
        logging.info("Conexión a SharePoint establecida correctamente")

    def setup_dropbox(self):
        """Configura la conexión con Dropbox Business y selecciona el miembro por email"""
        app_key       = os.getenv('DROPBOX_APP_KEY')
        app_secret    = os.getenv('DROPBOX_APP_SECRET')
        refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
        member_email  = os.getenv('DROPBOX_MEMBER_EMAIL')

        if not all([app_key, app_secret, refresh_token, member_email]):
            raise ValueError("Faltan variables de Dropbox en .env: DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN, DROPBOX_MEMBER_EMAIL")

        # Conecta al equipo
        team_client = DropboxTeam(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )

        # Busca el team_member_id por email
        logging.info(f"Buscando miembro en el team: %s", member_email)
        result = team_client.team_members_list()
        team_member_id = None
        for m in result.members:
            if m.profile.email.lower() == member_email.lower():
                team_member_id = m.profile.team_member_id
                break
        if not team_member_id:
            raise ValueError(f"No encontré a {member_email} en el equipo de Dropbox")

        # Impersona al usuario
        self.dbx = team_client.as_user(team_member_id)
        logging.info("Impersonación OK para %s -> %s", member_email, team_member_id)

    def download_from_sharepoint(self, file_url):
        """Descarga un archivo desde SharePoint y retorna su contenido en bytes"""
        try:
            response = File.open_binary(self.ctx, file_url)
            return response.content
        except Exception as e:
            logging.error("Error al descargar %s: %s", file_url, e)
            return None

    @rate_limited(2)
    def upload_to_dropbox(self, file_content, dropbox_path, chunk_size=4*1024*1024):
        """
        Sube un archivo a Dropbox Business impersonado
        Si el archivo es mayor a 150 MB, utiliza carga en sesiones (chunked upload).
        
        Args:
            file_content (bytes): Contenido del archivo.
            dropbox_path (str): Ruta de destino en Dropbox.
            chunk_size (int, opcional): Tamaño de cada chunk en bytes. Por defecto, 4 MB.
        
        Returns:
            bool: True si la subida fue exitosa, False en caso contrario.
        """
        try:
            size = len(file_content)
            threshold = 150 * 1024 * 1024
            if size <= threshold:
                self.dbx.files_upload(file_content, dropbox_path, mode=WriteMode.overwrite)
                logging.info("Upload directo: %s", dropbox_path)
            else:
                stream = io.BytesIO(file_content)
                session = self.dbx.files_upload_session_start(stream.read(chunk_size))
                cursor = UploadSessionCursor(session.session_id, offset=stream.tell())
                commit = CommitInfo(path=dropbox_path, mode=WriteMode.overwrite)
                while stream.tell() < size:
                    if (size - stream.tell()) <= chunk_size:
                        self.dbx.files_upload_session_finish(stream.read(chunk_size), cursor, commit)
                    else:
                        self.dbx.files_upload_session_append_v2(stream.read(chunk_size), cursor)
                        cursor.offset = stream.tell()
                logging.info("Upload sesional: %s", dropbox_path)
            return True
        except Exception as e:
            logging.error("Error uploading %s: %s", dropbox_path, e)
            return False

    def migrate_file(self, sp_path, dbx_path):
        content = self.download_from_sharepoint(sp_path)
        if content:
            if self.upload_to_dropbox(content, dbx_path):
                logging.info("Migrado: %s -> %s", sp_path, dbx_path)
                return True
        return False

    def start_migration(self, source_folder, target_folder):
        folder = self.ctx.web.get_folder_by_server_relative_url(source_folder).expand(["Files", "Folders"])
        self.ctx.load(folder)
        self.ctx.execute_query()
        files = folder.files
        subs  = folder.folders
        try:
            self.dbx.files_create_folder_v2(target_folder)
        except Exception:
            pass
        logging.info("'%s': %d archivos, %d subfolders", source_folder, len(files), len(subs))
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = []
            for f in files:
                sp = f.serverRelativeUrl
                db = f"{target_folder}/{f.properties['Name']}"
                futures.append(ex.submit(self.migrate_file, sp, db))
            for _ in tqdm(futures, desc=f"Migrando {source_folder}", unit="file"):
                pass
        for sub in subs:
            name = sub.properties['Name']
            self.start_migration(sub.serverRelativeUrl, f"{target_folder}/{name}")

if __name__ == "__main__":
    try:
        migrator = SharePointToDropboxMigrator()
        sp_folder  = os.getenv('SHAREPOINT_FOLDER')
        dbx_folder = os.getenv('DROPBOX_FOLDER')
        if not all([sp_folder, dbx_folder]):
            raise ValueError("Faltan SHAREPOINT_FOLDER o DROPBOX_FOLDER en el .env")
        migrator.start_migration(sp_folder, dbx_folder)
    except Exception as err:
        logging.error("Error en ejecución: %s", err)
        sys.exit(1)
