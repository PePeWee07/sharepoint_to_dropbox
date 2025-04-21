# get_refresh_token.py
from dropbox.oauth import DropboxOAuth2FlowNoRedirect
import os
from dotenv import load_dotenv
load_dotenv()

APP_KEY    = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")

# Inicia el flujo OAuth2 pidiendo offline (refresh token)
flow = DropboxOAuth2FlowNoRedirect(
    consumer_key=APP_KEY,
    consumer_secret=APP_SECRET,
    token_access_type="offline"
)

# 1) Abre la URL e inicia sesión en Dropbox autorizando tu app
print("1) Ve a esta URL en tu navegador y autoriza tu app:")
print(flow.start())
print()

# 2) Pega aquí el código que copie Dropbox tras autorizar
code = input("2) Introduce el código y pulsa Enter: ").strip()

# 3) Intercambia el código por tokens
oauth_result = flow.finish(code)
print("\n— Tokens obtenidos —")
print("Access token (4 h):", oauth_result.access_token)
print("Refresh token (persistente):", oauth_result.refresh_token)
print("\n¡Guarda especialmente el refresh_token en tu .env!")
