"""Vigilante de directos: avisa cuando acaba un directo de los canales de canales.json.

Lo ejecuta GitHub Actions cada 10 minutos (gratis en un repositorio público). No usa claves: lee lo mismo
que cualquier visitante con yt-dlp. Guarda en estado.json quién estaba en directo, y cuando un canal pasa de
"en directo" a "no en directo" escribe el aviso en avisos.json; el workflow lo convierte en un issue de GitHub,
que llega por correo.
"""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))


def yt(args):
    r = subprocess.run(["yt-dlp", "--no-warnings", "--no-update"] + args, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip()


def en_directo(url):
    codigo, salida = yt(["--print", "%(title)s", url])
    return (codigo == 0 and bool(salida)), salida


def ultimo_vod_twitch(canal):
    codigo, salida = yt(["--flat-playlist", "--playlist-end", "1", "--print", "%(id)s",
                         "https://www.twitch.tv/%s/videos?filter=archives&sort=time" % canal])
    return salida.splitlines()[-1].lstrip("v") if codigo == 0 and salida else None


def revisar(plataforma, canal):
    url = "https://www.twitch.tv/%s" % canal if plataforma == "twitch" else "https://kick.com/%s" % canal
    vivo, titulo = en_directo(url)
    vod = ultimo_vod_twitch(canal) if plataforma == "twitch" and not vivo else None
    return plataforma, canal, vivo, titulo, vod


def main():
    with open(os.path.join(AQUI, "canales.json"), encoding="utf-8") as f:
        canales = json.load(f)
    ruta_estado = os.path.join(AQUI, "estado.json")
    estado = {}
    if os.path.exists(ruta_estado):
        with open(ruta_estado, encoding="utf-8") as f:
            estado = json.load(f)
    tareas = [(p, c) for p in ("twitch", "kick") for c in canales.get(p, [])]
    with ThreadPoolExecutor(max_workers=12) as ex:
        resultados = list(ex.map(lambda t: revisar(*t), tareas))
    avisos = []
    for plataforma, canal, vivo, titulo, vod in resultados:
        clave = "%s/%s" % (plataforma, canal)
        antes = estado.get(clave, {})
        if vivo:
            estado[clave] = {"vivo": True, "titulo": titulo or antes.get("titulo", ""), "vod": antes.get("vod")}
            continue
        if antes.get("vivo"):
            enlace = ("https://www.twitch.tv/videos/%s" % vod) if vod else ("https://kick.com/%s" % canal)
            avisos.append({"canal": canal, "plataforma": plataforma, "titulo": antes.get("titulo", ""), "enlace": enlace,
                           "gta": "gta" in (antes.get("titulo", "") or "").lower()})
        estado[clave] = {"vivo": False, "titulo": antes.get("titulo", ""), "vod": vod or antes.get("vod")}
    with open(ruta_estado, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(AQUI, "avisos.json"), "w", encoding="utf-8") as f:
        json.dump(avisos, f, ensure_ascii=False)
    vivos = [k for k, v in estado.items() if v.get("vivo")]
    print("En directo ahora: %s" % (", ".join(vivos) or "nadie"))
    print("Directos terminados: %d" % len(avisos))


if __name__ == "__main__":
    main()
