# Import libraries
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.client_credential import ClientCredential

import os
from dotenv import load_dotenv
load_dotenv()

# 2) Lee variables de entorno
SP_CLIENT_ID     = os.getenv("SHAREPOINT_CLIENT_ID")
SP_CLIENT_SECRET = os.getenv("SHAREPOINT_CLIENT_SECRET")
SP_URL      = os.getenv("SHAREPOINT_SITE_URL")
relative_folder_url   = os.getenv("SHAREPOINT_FOLDER")
# App-based authentication with access credentials
context = ClientContext(SP_URL).with_credentials(ClientCredential(SP_CLIENT_ID, SP_CLIENT_SECRET))
folder = context.web.get_folder_by_server_relative_url(relative_folder_url).expand(["Files"])
context.load(folder)
context.execute_query()

# Processes each Sharepoint file in folder
for file in folder.files:
    print(f'Processing file: {file.properties["Name"]}')
