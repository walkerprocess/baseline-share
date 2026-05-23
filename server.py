from http import cookies
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import secrets
import sqlite3
import time


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "baseline_share.db"))
ARCHIVE_DIR = ROOT / "assets" / "project-zips"
SESSION_SECONDS = 60 * 60 * 24 * 30
AD_SECONDS = 5
APP_ENV = os.environ.get("APP_ENV", "development")
ADS_TXT_CONTENT = os.environ.get("ADS_TXT_CONTENT", "").strip()
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


SEED_PROJECTS = [
    ("react-saas-dashboard", "React SaaS Dashboard", "Frontend", ["React", "Charts", "Auth UI"], 1284, "#2563eb", "react-saas-dashboard.zip", "A clean dashboard baseline with sidebar navigation, KPI cards, chart panels, and account settings."),
    ("fastapi-starter", "FastAPI Auth Starter", "Backend", ["Python", "FastAPI", "JWT"], 942, "#0f766e", "fastapi-auth-starter.zip", "REST API starter with auth routes, user models, request validation, and environment setup notes."),
    ("analytics-pipeline", "Analytics Pipeline Kit", "Analytics", ["Python", "CSV", "Reports"], 1138, "#7c3aed", "analytics-pipeline-kit.zip", "A reproducible analysis baseline for cleaning data, calculating KPIs, and exporting Markdown reports."),
    ("ai-chatbot-rag", "RAG Chatbot Baseline", "AI", ["Python", "RAG", "Vectors"], 756, "#db2777", "rag-chatbot-baseline.zip", "Document Q&A starter with ingestion steps, retrieval flow, prompt templates, and evaluation checklist."),
    ("product-roadmap", "Product Roadmap Workspace", "Product", ["HTML", "LocalStorage", "UX"], 481, "#0891b2", "product-roadmap-workspace.zip", "A product planning baseline with user stories, roadmap swimlanes, prioritization scoring, and notes."),
    ("codex-encrypted-chatroom", "Encrypted Chatroom Portfolio Baseline", "Security", ["Node", "WebSocket", "Web Crypto", "HTTPS"], 0, "#ea580c", "encrypted-chatroom.zip", "Resume-ready secure chatroom project with encrypted browser messages, WebSocket relay, private rooms, and security notes."),
    ("codex-logistics-news-analytics", "Live Logistics News Analytics", "Analytics", ["Python", "RSS News", "SQL", "Reports"], 0, "#0f766e", "live-logistics-news-analytics.zip", "Analytics portfolio baseline that turns live logistics news and shipment sample data into KPI and risk reports."),
    ("codex-jobfit-resume-intelligence", "JobFit Resume Intelligence", "Career", ["Python", "Jobs API", "News RSS", "Scoring"], 0, "#7c3aed", "jobfit-resume-intelligence.zip", "Career-tech baseline for students: score live jobs against a resume profile and generate a portfolio-ready job-fit report."),
    ("codex-stock-signal-engine", "Stock Signal Engine", "Finance", ["Python", "Yahoo Finance", "News RSS", "Excel"], 0, "#2563eb", "stock-signal-engine.zip", "Explainable stock screening project that ranks hot tickers with price momentum, news buzz, risk scoring, portfolio input, and Excel reporting."),
]

DEPRECATED_PROJECT_IDS = ["secure-chatroom"]


def now() -> int:
    return int(time.time())


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              credits INTEGER NOT NULL DEFAULT 0,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              created_at INTEGER NOT NULL,
              expires_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              category TEXT NOT NULL,
              stack_json TEXT NOT NULL,
              downloads_seed INTEGER NOT NULL DEFAULT 0,
              download_count INTEGER NOT NULL DEFAULT 0,
              color TEXT NOT NULL,
              file_name TEXT NOT NULL,
              description TEXT NOT NULL,
              uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS favorites (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              created_at INTEGER NOT NULL,
              PRIMARY KEY (user_id, project_id)
            );

            CREATE TABLE IF NOT EXISTS downloads (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              method TEXT NOT NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ad_unlocks (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              created_at INTEGER NOT NULL,
              expires_at INTEGER NOT NULL,
              used INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        for project_id in DEPRECATED_PROJECT_IDS:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        for project in SEED_PROJECTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO projects
                (id, title, category, stack_json, downloads_seed, color, file_name, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*project[:3], json.dumps(project[3]), project[4], project[5], project[6], project[7], now()),
            )


def slugify(value: str) -> str:
    clean = []
    prev_dash = False
    for char in value.lower():
        if char.isalnum():
            clean.append(char)
            prev_dash = False
        elif not prev_dash:
            clean.append("-")
            prev_dash = True
    return "".join(clean).strip("-") or "baseline-project"


def project_to_dict(row: sqlite3.Row) -> dict:
    archive_path = ARCHIVE_DIR / row["file_name"]
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "stack": json.loads(row["stack_json"]),
        "downloads": row["downloads_seed"] + row["download_count"],
        "color": row["color"],
        "file": row["file_name"],
        "description": row["description"],
        "uploadedBy": row["uploaded_by"],
        "createdAt": row["created_at"],
        "hasArchive": archive_path.exists(),
    }


def user_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "credits": row["credits"],
    }


class BaselineShareHandler(SimpleHTTPRequestHandler):
    server_version = "BaselineShare/0.1"

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        safe_path = parsed.path.lstrip("/") or "index.html"
        candidate = (ROOT / safe_path).resolve()
        if not str(candidate).startswith(str(ROOT)):
            return str(ROOT / "index.html")
        if candidate.is_dir():
            candidate = candidate / "index.html"
        return str(candidate)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            return self.json_response({"ok": True, "service": "baseline-share"})
        if path == "/ads.txt":
            return self.ads_txt()
        if path == "/api/bootstrap":
            return self.bootstrap()
        if path.startswith("/api/projects/") and path.endswith("/download"):
            project_id = path.split("/")[3]
            return self.project_download(project_id)
        if path.startswith("/api/projects/") and path.endswith("/manifest"):
            project_id = path.split("/")[3]
            return self.project_manifest(project_id)
        if path.startswith("/api/"):
            return self.json_response({"error": "Not found"}, 404)
        return super().do_GET()

    def ads_txt(self) -> None:
        if not ADS_TXT_CONTENT:
            body = "# ads.txt is not configured yet. Add ADS_TXT_CONTENT after an ad network approves this site.\n".encode("utf-8")
            self.send_response(200)
        else:
            body = f"{ADS_TXT_CONTENT}\n".encode("utf-8")
            self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        routes = {
            "/api/auth/login": self.login,
            "/api/auth/logout": self.logout,
            "/api/projects": self.create_project,
            "/api/favorites/toggle": self.toggle_favorite,
            "/api/downloads/start": self.start_download,
            "/api/downloads/complete-ad": self.complete_ad_download,
        }
        handler = routes.get(path)
        if not handler:
            return self.json_response({"error": "Not found"}, 404)
        return handler()

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def read_multipart(self) -> tuple[dict, dict | None]:
        content_type = self.headers.get("Content-Type", "")
        boundary_marker = "boundary="
        if boundary_marker not in content_type:
            raise ValueError("Multipart boundary missing")
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            raise ValueError("Upload body missing")
        if length > MAX_UPLOAD_BYTES:
            raise ValueError("Upload is too large. Please keep zip files under 25MB.")

        boundary = content_type.split(boundary_marker, 1)[1].strip().strip('"')
        body = self.rfile.read(length)
        fields: dict[str, str] = {}
        upload: dict | None = None

        for raw_part in body.split(("--" + boundary).encode("utf-8")):
            part = raw_part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            if b"\r\n\r\n" not in part:
                continue
            header_blob, content = part.split(b"\r\n\r\n", 1)
            headers = header_blob.decode("utf-8", "replace").split("\r\n")
            disposition = next((header for header in headers if header.lower().startswith("content-disposition:")), "")
            params = {}
            for item in disposition.split(";"):
                if "=" in item:
                    key, value = item.strip().split("=", 1)
                    params[key.lower()] = value.strip().strip('"')
            name = params.get("name")
            filename = params.get("filename")
            content = content.rstrip(b"\r\n")
            if not name:
                continue
            if filename:
                upload = {"field": name, "filename": filename, "content": content}
            else:
                fields[name] = content.decode("utf-8", "replace").strip()

        return fields, upload

    def json_response(self, payload: dict, status: int = 200, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def current_user(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        cookie_header = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie(cookie_header)
        token = jar.get("baseline_session")
        if not token:
            return None
        row = conn.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ? AND sessions.expires_at > ?
            """,
            (token.value, now()),
        ).fetchone()
        return row

    def require_user(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        user = self.current_user(conn)
        if not user:
            self.json_response({"error": "Login required"}, 401)
            return None
        return user

    def bootstrap(self) -> None:
        with db() as conn:
            user = self.current_user(conn)
            projects = [project_to_dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY created_at DESC")]
            favorites = []
            downloads = []
            if user:
                favorites = [
                    row["project_id"]
                    for row in conn.execute("SELECT project_id FROM favorites WHERE user_id = ?", (user["id"],))
                ]
                downloads = [
                    {
                        "id": row["project_id"],
                        "title": row["title"],
                        "method": row["method"],
                        "time": row["created_at"] * 1000,
                    }
                    for row in conn.execute(
                        """
                        SELECT downloads.project_id, projects.title, downloads.method, downloads.created_at
                        FROM downloads
                        JOIN projects ON projects.id = downloads.project_id
                        WHERE downloads.user_id = ?
                        ORDER BY downloads.created_at DESC
                        """,
                        (user["id"],),
                    )
                ]
            stats = {
                "projects": len(projects),
                "downloads": len(downloads),
                "uploads": conn.execute("SELECT COUNT(*) AS count FROM projects WHERE uploaded_by IS NOT NULL").fetchone()["count"],
                "favorites": len(favorites),
            }
            self.json_response({
                "user": user_to_dict(user) if user else None,
                "credits": user["credits"] if user else 0,
                "projects": projects,
                "favorites": favorites,
                "downloads": downloads,
                "stats": stats,
            })

    def login(self) -> None:
        data = self.read_json()
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        if not name or "@" not in email:
            return self.json_response({"error": "Valid name and email required"}, 400)

        with db() as conn:
            conn.execute(
                "INSERT INTO users (email, name, created_at) VALUES (?, ?, ?) ON CONFLICT(email) DO UPDATE SET name = excluded.name",
                (email, name, now()),
            )
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user["id"], now(), now() + SESSION_SECONDS),
            )

        session_cookie = cookies.SimpleCookie()
        session_cookie["baseline_session"] = token
        session_cookie["baseline_session"]["path"] = "/"
        session_cookie["baseline_session"]["max-age"] = str(SESSION_SECONDS)
        session_cookie["baseline_session"]["httponly"] = True
        session_cookie["baseline_session"]["samesite"] = "Lax"
        if APP_ENV == "production":
            session_cookie["baseline_session"]["secure"] = True
        self.json_response({"ok": True, "user": user_to_dict(user)}, extra_headers={"Set-Cookie": session_cookie.output(header="").strip()})

    def logout(self) -> None:
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        token = jar.get("baseline_session")
        with db() as conn:
            if token:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token.value,))
        expired = "baseline_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
        if APP_ENV == "production":
            expired += "; Secure"
        self.json_response({"ok": True}, extra_headers={"Set-Cookie": expired})

    def create_project(self) -> None:
        with db() as conn:
            user = self.require_user(conn)
            if not user:
                return
            content_type = self.headers.get("Content-Type", "")
            upload = None
            if content_type.startswith("multipart/form-data"):
                try:
                    data, upload = self.read_multipart()
                except ValueError as error:
                    return self.json_response({"error": str(error)}, 400)
            else:
                data = self.read_json()
            title = str(data.get("title", "")).strip()
            category = str(data.get("category", "")).strip()
            stack = [item.strip() for item in str(data.get("stack", "")).split(",") if item.strip()][:4]
            description = str(data.get("description", "")).strip()
            if not title or not category or not stack or not description:
                return self.json_response({"error": "Title, category, stack, and description are required"}, 400)
            if not upload or upload.get("field") != "archive":
                return self.json_response({"error": "A project zip file is required"}, 400)
            if not upload["filename"].lower().endswith(".zip") or not upload["content"].startswith(b"PK"):
                return self.json_response({"error": "Upload must be a valid zip file"}, 400)

            base_id = slugify(title)
            project_id = f"{base_id}-{secrets.token_hex(3)}"
            file_name = f"{project_id}.zip"
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            (ARCHIVE_DIR / file_name).write_bytes(upload["content"])
            conn.execute(
                """
                INSERT INTO projects
                (id, title, category, stack_json, color, file_name, description, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, title, category, json.dumps(stack), "#334155", file_name, description, user["id"], now()),
            )
            conn.execute("UPDATE users SET credits = credits + 5 WHERE id = ?", (user["id"],))
        self.bootstrap()

    def toggle_favorite(self) -> None:
        with db() as conn:
            user = self.require_user(conn)
            if not user:
                return
            project_id = str(self.read_json().get("project_id", ""))
            if not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
                return self.json_response({"error": "Project not found"}, 404)
            existing = conn.execute("SELECT 1 FROM favorites WHERE user_id = ? AND project_id = ?", (user["id"], project_id)).fetchone()
            if existing:
                conn.execute("DELETE FROM favorites WHERE user_id = ? AND project_id = ?", (user["id"], project_id))
            else:
                conn.execute("INSERT INTO favorites (user_id, project_id, created_at) VALUES (?, ?, ?)", (user["id"], project_id, now()))
        self.bootstrap()

    def start_download(self) -> None:
        with db() as conn:
            user = self.require_user(conn)
            if not user:
                return
            project_id = str(self.read_json().get("project_id", ""))
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                return self.json_response({"error": "Project not found"}, 404)

            fresh_user = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            if fresh_user["credits"] > 0:
                conn.execute("UPDATE users SET credits = credits - 1 WHERE id = ?", (user["id"],))
                self.record_download(conn, user["id"], project_id, "ad-free upload credit")
                should_bootstrap = True
            else:
                should_bootstrap = False

            if not should_bootstrap:
                token = secrets.token_urlsafe(24)
                conn.execute(
                    "INSERT INTO ad_unlocks (token, user_id, project_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (token, user["id"], project_id, now(), now() + 600),
                )
                ad_payload = {"requiresAd": True, "adToken": token, "project": project_to_dict(project), "seconds": AD_SECONDS}
            else:
                ad_payload = None

        if should_bootstrap:
            self.bootstrap()
        else:
            self.json_response(ad_payload)

    def complete_ad_download(self) -> None:
        with db() as conn:
            user = self.require_user(conn)
            if not user:
                return
            token = str(self.read_json().get("ad_token", ""))
            unlock = conn.execute(
                "SELECT * FROM ad_unlocks WHERE token = ? AND user_id = ? AND used = 0",
                (token, user["id"]),
            ).fetchone()
            if not unlock:
                return self.json_response({"error": "Ad unlock not found"}, 404)
            if unlock["expires_at"] < now():
                return self.json_response({"error": "Ad unlock expired"}, 410)
            if now() - unlock["created_at"] < AD_SECONDS:
                return self.json_response({"error": "Sponsor view is still running"}, 409)

            conn.execute("UPDATE ad_unlocks SET used = 1 WHERE token = ?", (token,))
            self.record_download(conn, user["id"], unlock["project_id"], "sponsor view")
        self.bootstrap()

    def record_download(self, conn: sqlite3.Connection, user_id: int, project_id: str, method: str) -> None:
        conn.execute(
            "INSERT INTO downloads (user_id, project_id, method, created_at) VALUES (?, ?, ?, ?)",
            (user_id, project_id, method, now()),
        )
        conn.execute("UPDATE projects SET download_count = download_count + 1 WHERE id = ?", (project_id,))

    def project_manifest(self, project_id: str) -> None:
        with db() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                return self.json_response({"error": "Project not found"}, 404)
            data = project_to_dict(project)
        body = "\n".join([
            f"Baseline Share download: {data['title']}",
            "",
            data["description"],
            "",
            f"Stack: {', '.join(data['stack'])}",
            "This prototype returns a manifest. Production should stream the real project archive from object storage.",
        ]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=\"{data['file'].replace('.zip', '-manifest.txt')}\"")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def project_download(self, project_id: str) -> None:
        with db() as conn:
            project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                return self.json_response({"error": "Project not found"}, 404)
            data = project_to_dict(project)

        archive_path = (ARCHIVE_DIR / data["file"]).resolve()
        archive_root = ARCHIVE_DIR.resolve()
        if str(archive_path).startswith(str(archive_root)) and archive_path.exists():
            body = archive_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f"attachment; filename=\"{data['file']}\"")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.project_manifest(project_id)


if __name__ == "__main__":
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "4178"))
    server = ThreadingHTTPServer((host, port), BaselineShareHandler)
    print(f"Baseline Share backend running at http://{host}:{port}")
    server.serve_forever()
