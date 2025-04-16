import os
import sys
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
import dropbox
from tqdm import tqdm
from dotenv import load_dotenv
import logging
from concurrent.futures import ThreadPoolExecutor
import time
import io
import functools

def rate_limited(max_per_second):
    """
    Decorador para limitar la cantidad de llamadas a la función.
    
    Args:
        max_per_second (int): Número máximo de llamadas permitidas por segundo.
    
    Retorna:
        función decorada que respeta el límite de llamadas.
    """
    min_interval = 1.0 / float(max_per_second)
    
    def decorator(func):
        last_call = [0.0]  # Lista mutable para almacenar el último tiempo de llamada
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
    """Clase para migrar archivos desde SharePoint a Dropbox de forma automatizada."""
    def __init__(self):
        load_dotenv()
        self.setup_sharepoint()
        self.setup_dropbox()

    def setup_sharepoint(self):
        """Configura la conexión con SharePoint"""
        try:
            client_id = os.getenv('SHAREPOINT_CLIENT_ID')
            client_secret = os.getenv('SHAREPOINT_CLIENT_SECRET')
            site_url = os.getenv('SHAREPOINT_SITE_URL')
            if not all([client_id, client_secret, site_url]):
                raise ValueError("Faltan credenciales de SharePoint en el archivo .env")

            credentials = ClientCredential(client_id, client_secret)
            self.ctx = ClientContext(site_url).with_credentials(credentials)
            
            # Realizar una consulta de prueba para validar la conexión
            web = self.ctx.web
            self.ctx.load(web)
            self.ctx.execute_query()
            
            logging.info("Conexión a SharePoint establecida correctamente")
        except (ValueError, Exception) as sharepoint_error:
            logging.error("Error al configurar SharePoint: %s", str(sharepoint_error))
            raise

    def setup_dropbox(self):
        """Configura la conexión con Dropbox"""
        try:
            access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
            if not access_token:
                raise ValueError("Falta el token de acceso de Dropbox en el archivo .env")

            self.dbx = dropbox.Dropbox(access_token)
            # Realiza una llamada a la API para verificar el token
            self.dbx.users_get_current_account()
            logging.info("Conexión a Dropbox establecida correctamente")
        except (ValueError, Exception) as dropbox_error:
            logging.error("Error al configurar Dropbox: %s", str(dropbox_error))
            raise

    def download_from_sharepoint(self, file_url):
        """Descarga un archivo desde SharePoint"""
        try:
            file = File.open_binary(self.ctx, file_url)
            return file
        except (ValueError, IOError, RuntimeError) as download_error:
            logging.error("Error al descargar %s: %s", file_url, str(download_error))
            return None

    @rate_limited(2)  # Limita a 2 llamadas por segundo (puedes ajustar este valor)
    def upload_to_dropbox(self, file_content, dropbox_path, chunk_size=4 * 1024 * 1024):
        """
        Sube un archivo a Dropbox.
        Si el archivo es mayor a 150 MB, utiliza carga en sesiones (chunked upload).
        
        Args:
            file_content (bytes): Contenido del archivo.
            dropbox_path (str): Ruta de destino en Dropbox.
            chunk_size (int, opcional): Tamaño de cada chunk en bytes. Por defecto, 4 MB.
        
        Returns:
            bool: True si la subida fue exitosa, False en caso contrario.
        """
        try:
            file_size = len(file_content)
            threshold = 150 * 1024 * 1024  # 150 MB de umbral
            
            if file_size <= threshold:
                self.dbx.files_upload(file_content, dropbox_path)
                logging.info("Archivo subido exitosamente (carga directa): %s", dropbox_path)
            else:
                stream = io.BytesIO(file_content)
                # Inicia la sesión de carga leyendo el primer chunk
                session_start_result = self.dbx.files_upload_session_start(stream.read(chunk_size))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=session_start_result.session_id,
                    offset=stream.tell()
                )
                commit = dropbox.files.CommitInfo(path=dropbox_path)
                
                # Envía el archivo en chunks
                while stream.tell() < file_size:
                    if (file_size - stream.tell()) <= chunk_size:
                        self.dbx.files_upload_session_finish(stream.read(chunk_size), cursor, commit)
                    else:
                        self.dbx.files_upload_session_append_v2(stream.read(chunk_size), cursor)
                        cursor.offset = stream.tell()
                logging.info("Archivo subido exitosamente (carga en sesiones): %s", dropbox_path)
            return True
        except (dropbox.exceptions.ApiError, IOError) as upload_error:
            logging.error("Error al subir %s: %s", dropbox_path, str(upload_error))
            return False

    def migrate_file(self, sharepoint_path, dropbox_path):
        """Migra un archivo individual"""
        try:
            file_content = self.download_from_sharepoint(sharepoint_path)
            if file_content:
                success = self.upload_to_dropbox(file_content, dropbox_path)
                if success:
                    logging.info("Archivo migrado exitosamente: %s -> %s", sharepoint_path, dropbox_path)
                    return True
            return False
        except (ValueError, IOError, RuntimeError, dropbox.exceptions.ApiError) as migration_error:
            logging.error("Error en la migración de %s: %s", sharepoint_path, str(migration_error))
            return False

    def start_migration(self, source_folder, target_folder):
        """Inicia el proceso de migración"""
        try:
            # Obtener lista de archivos de SharePoint
            folder = self.ctx.web.get_folder_by_server_relative_url(source_folder)
            files = folder.files
            self.ctx.load(files)
            self.ctx.execute_query()

            total_files = len(files)
            logging.info("Total de archivos a migrar: %d", total_files)

            # Usar ThreadPoolExecutor para migración paralela
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for file in files:
                    sharepoint_path = file.serverRelativeUrl
                    dropbox_path = f"{target_folder}/{os.path.basename(sharepoint_path)}"
                    futures.append(
                        executor.submit(self.migrate_file, sharepoint_path, dropbox_path)
                    )

                # Mostrar barra de progreso
                with tqdm(total=total_files, desc="Migrando archivos") as pbar:
                    for future in futures:
                        future.result()
                        pbar.update(1)

            logging.info("Migración completada")
        except Exception as migration_process_error:
            logging.error("Error durante la migración: %s", str(migration_process_error))
            raise

if __name__ == "__main__":
    try:
        migrator = SharePointToDropboxMigrator()
        sharepoint_folder = os.getenv('SHAREPOINT_FOLDER')
        dropbox_folder = os.getenv('DROPBOX_FOLDER')

        if not all([sharepoint_folder, dropbox_folder]):
            raise ValueError("Faltan rutas de carpetas en el archivo .env")
        migrator.start_migration(sharepoint_folder, dropbox_folder)
    except Exception as main_error:
        logging.error("Error en la ejecución del script: %s", str(main_error))
        sys.exit(1)