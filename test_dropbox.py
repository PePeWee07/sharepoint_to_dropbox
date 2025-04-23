# test_dropbox.py

import os
from dotenv import load_dotenv
from dropbox import DropboxTeam
from dropbox.files import FileMetadata, FolderMetadata
import logging

def main():
    load_dotenv()

    # Lee tus credenciales y datos del .env
    APP_KEY          = os.getenv("DROPBOX_APP_KEY")
    APP_SECRET       = os.getenv("DROPBOX_APP_SECRET")
    REFRESH_TOKEN    = os.getenv("DROPBOX_REFRESH_TOKEN")
    MEMBER_EMAIL     = os.getenv("DROPBOX_MEMBER_EMAIL")     # p.ej. jose.roman@ucacue.edu.ec
    DROPBOX_FOLDER   = os.getenv("DROPBOX_FOLDER", "")      # p.ej. "/Miembros/jose.roman"

    # 1) Conecta como equipo
    team_client = DropboxTeam(
        app_key=APP_KEY,
        app_secret=APP_SECRET,
        oauth2_refresh_token=REFRESH_TOKEN
    )

    # 2) Busca el team_member_id por email
    print(f"🔍 Buscando miembro {MEMBER_EMAIL} en el equipo…")
    result = team_client.team_members_list()
    team_member_id = None
    for m in result.members:
        if m.profile.email.lower() == MEMBER_EMAIL.lower():
            team_member_id = m.profile.team_member_id
            break

    if not team_member_id:
        print(f"❌ No encontré a {MEMBER_EMAIL} en tu equipo.")
        return

    print(f"✅ Encontrado: {MEMBER_EMAIL} → team_member_id={team_member_id}\n")

    # 3) Impersona al miembro con su ID
    member = team_client.as_user(team_member_id)
    acct = member.users_get_current_account()
    print(f"👤 Actuando como: {acct.email} ({acct.name.display_name})\n")

    # 4) Lista la carpeta destino en su espacio
    print(f"📂 Contenido de '{DROPBOX_FOLDER}':")
    res = member.files_list_folder(DROPBOX_FOLDER)
    for entry in res.entries:
        if isinstance(entry, FolderMetadata):
            kind = "folder"
        elif isinstance(entry, FileMetadata):
            kind = "file"
        else:
            kind = "unknown"
        print(f" - {entry.name} ({kind})")

    while res.has_more:
        res = member.files_list_folder_continue(res.cursor)
        for entry in res.entries:
            if isinstance(entry, FolderMetadata):
                kind = "folder"
            elif isinstance(entry, FileMetadata):
                kind = "file"
            else:
                kind = "unknown"
            print(f" - {entry.name} ({kind})")
    
    # Listado recursivo de TODOS los elementos desde la raíz
    # print("🔍 Listado recursivo de TODO el árbol:")
    # res = member.files_list_folder(path="", recursive=True)

    # for entry in res.entries:
    #     print(f" - {entry.path_display}")

    # # Paginación
    # while res.has_more:
    #     res = member.files_list_folder_continue(res.cursor)
    #     for entry in res.entries:
    #         print(f" - {entry.path_display}")



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
