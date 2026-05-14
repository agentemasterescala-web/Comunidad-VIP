#!/usr/bin/env python3
"""
Servidor local para el Panel Comunidad VIP.

Sirve el dashboard.html en http://localhost:8888 y expone un endpoint
POST /api/send-email que envía correos vía Gmail SMTP usando un App
Password configurado en el .env.

Variables del .env requeridas:
  GMAIL_FROM            correo corporativo desde el que se envía
  GMAIL_APP_PASSWORD    App Password de Google (16 caracteres)
  GMAIL_FROM_NAME       (opcional) nombre visible en el From
  PORT_LOCAL            (opcional, por defecto 8888)

Arrancar:    python3 servidor_local.py
Detener:     Ctrl+C
"""
import os, json, ssl, smtplib, sys, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
DASHBOARD_PATH = os.path.join(HERE, "dashboard.html")


def load_env():
    env = {}
    if os.path.isfile(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip()
                    # Strip inline comment ' # ...' for unquoted values
                    # (same behavior as Bash `source`)
                    if v and v[0] not in ('"', "'"):
                        hash_pos = v.find(" #")
                        if hash_pos >= 0:
                            v = v[:hash_pos].rstrip()
                    env[k.strip()] = v.strip('"').strip("'")
    return env


ENV = load_env()
PORT = int(ENV.get("PORT_LOCAL", "8888"))
GMAIL_FROM = ENV.get("GMAIL_FROM", "")
GMAIL_APP_PASSWORD = ENV.get("GMAIL_APP_PASSWORD", "")
GMAIL_FROM_NAME = ENV.get("GMAIL_FROM_NAME", "")


def send_email_smtp(to, subject, body_html, body_text=None):
    if not GMAIL_FROM or not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_FROM y/o GMAIL_APP_PASSWORD no configurados en .env"
        )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((GMAIL_FROM_NAME or "", GMAIL_FROM))
    msg["To"] = to
    if not body_text:
        # Fallback: quitar tags HTML básicos
        import re
        body_text = re.sub(r"<[^>]+>", "", body_html)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as srv:
        srv.starttls(context=ctx)
        srv.login(GMAIL_FROM, GMAIL_APP_PASSWORD)
        srv.sendmail(GMAIL_FROM, [to], msg.as_string())


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/dashboard.html", "/index.html"):
            self._send_file(DASHBOARD_PATH, "text/html; charset=utf-8")
        elif p == "/api/config":
            self._send_json(200, {
                "ready": bool(GMAIL_FROM and GMAIL_APP_PASSWORD),
                "from_email": GMAIL_FROM,
                "from_name": GMAIL_FROM_NAME,
                "server": "ok",
            })
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw or "{}")
        except Exception as e:
            self._send_json(400, {"error": f"JSON inválido: {e}"}); return
        if p == "/api/send-email":
            self._handle_send(payload)
        else:
            self._send_json(404, {"error": "no encontrado"})

    def _handle_send(self, payload):
        to = (payload.get("to") or "").strip()
        subject = payload.get("subject") or ""
        body_html = payload.get("body_html") or ""
        body_text = payload.get("body_text") or None
        if not to or "@" not in to:
            self._send_json(400, {"error": "destinatario inválido"}); return
        if not subject or not body_html:
            self._send_json(400, {"error": "asunto y cuerpo son obligatorios"}); return
        try:
            send_email_smtp(to, subject, body_html, body_text)
            print(f"  ✓ Email enviado a {to}")
            self._send_json(200, {"ok": True, "to": to})
        except smtplib.SMTPAuthenticationError as e:
            print(f"  ✗ Auth fallida ({to}): {e}")
            self._send_json(500, {"error": f"Autenticación fallida con Gmail. "
                                           f"Revisa GMAIL_FROM y GMAIL_APP_PASSWORD."})
        except Exception as e:
            print(f"  ✗ Error enviando a {to}: {e}")
            self._send_json(500, {"error": str(e)})

    def log_message(self, fmt, *a):
        # Silenciar logs de favicon/etc; solo mostrar APIs
        msg = fmt % a
        if "/api/" in msg or " 4" in msg or " 5" in msg:
            sys.stderr.write(f"[{self.log_date_time_string()}] {msg}\n")


def main():
    ready = bool(GMAIL_FROM and GMAIL_APP_PASSWORD)
    print()
    print("┌─────────────────────────────────────────────────────┐")
    print("│  Servidor local · Panel Comunidad VIP               │")
    print("├─────────────────────────────────────────────────────┤")
    print(f"│  URL:         http://localhost:{PORT}                  │")
    print(f"│  Gmail FROM:  {(GMAIL_FROM or '(no configurado)'):<38}│")
    print(f"│  Listo:       {'✓ SÍ' if ready else '✗ NO — completa .env primero':<38}│")
    print("└─────────────────────────────────────────────────────┘")
    print("  Ctrl+C para detener.")
    print()
    if not ready:
        print("⚠️  Faltan variables en .env:")
        if not GMAIL_FROM: print("     GMAIL_FROM=tu-correo@empresa.com")
        if not GMAIL_APP_PASSWORD: print("     GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx")
        print("  (el servidor arranca igual, pero los envíos fallarán)")
        print()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        srv.shutdown()


if __name__ == "__main__":
    main()
