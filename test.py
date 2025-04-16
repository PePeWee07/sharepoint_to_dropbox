import os
from dotenv import load_dotenv

# 1) Carga tu .env
load_dotenv()

from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

# 2) Lee variables de entorno
client_id     = os.getenv("SHAREPOINT_CLIENT_ID")
client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
site_url      = os.getenv("SHAREPOINT_SITE_URL")
folder_path   = os.getenv("SHAREPOINT_FOLDER")

# 3) Autenticación App-Only
credentials = ClientCredential(client_id, client_secret)
ctx = ClientContext(site_url).with_credentials(credentials)

# 4) Listado de archivos en la carpeta
target_folder = ctx.web.get_folder_by_server_relative_url(folder_path)
files = target_folder.files.get().execute_query()
for f in files:
    print(f.properties["Name"])
