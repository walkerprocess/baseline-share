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
SESSION_SECONDS = 60 * 60 * 24 * 30
AD_SECONDS = 5
APP_ENV = os.environ.get("APP_ENV", "development")


SEED_PROJECTS = [
    ("react-saas-dashboard", "React SaaS Dashboard", "Frontend", ["React", "Charts", "Auth UI"], 1284, "#2563eb", "react-saas-dashboard.zip", "A clean dashboard baseline with sidebar navigation, KPI cards, chart panels, and account settings."),
    ("fastapi-starter", "FastAPI Auth Starter", "Backend", ["Python", "FastAPI", "JWT"], 942, "#0f766e", "fastapi-auth-starter.zip", "REST API starter with auth routes, user models, request validation, and environment setup notes."),
    ("analytics-pipeline", "Analytics Pipeline Kit", "Analytics", ["Python", "CSV", "Reports"], 1138, "#7c3aed", "analytics-pipeline-kit.zip", "A reproducible analysis baseline for cleaning data, calculating KPIs, and exporting Markdown reports."),
    ("ai-chatbot-rag", "RAG Chatbot Baseline", "AI", ["Python", "RAG", "Vectors"], 756, "#db2777", "rag-chatbot-baseline.zip", "Document Q&A starter with ingestion steps, retrieval flow, prompt templates, and evaluation checklist."),
    ("secure-chatroom", "Encrypted Chatroom", "Security", ["Node", "WebSocket", "Crypto"], 618, "#ea580c", "encrypted-chatroom.zip", "Browser-side encryption starter with WebSocket relay, hashed rooms, and security notes."),
    ("product-roadmap", "Product Roadmap Workspace", "Product", ["HTML", "LocalStorage", "UX"], 481, "#0891b2", "product-roadmap-workspace.zip", "A product planning baseline with user stories, roadmap swimlanes, prioritization scoring, and notes."),
]


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
        if path == "/api/bootstrap":
            return self.bootstrap()
        if path.startswith("/api/projects/") and path.endswith("/manifest"):
            project_id = path.split("/")[3]
            return self.project_manifest(project_id)
        if path.startswith("/api/"):
            return self.json_response({"error": "Not found"}, 404)
        return super().do_GET()

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
            data = self.read_json()
            title = str(data.get("title", "")).strip()
            category = str(data.get("category", "")).strip()
            stack = [item.strip() for item in str(data.get("stack", "")).split(",") if item.strip()][:4]
            description = str(data.get("description", "")).strip()
            if not title or not category or not stack or not description:
                return self.json_response({"error": "Title, category, stack, and description are required"}, 400)

            base_id = slugify(title)
            project_id = f"{base_id}-{secrets.token_hex(3)}"
            conn.execute(
                """
                INSERT INTO projects
                (id, title, category, stack_json, color, file_name, description, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, title, category, json.dumps(stack), "#334155", f"{base_id}.zip", description, user["id"], now()),
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


if __name__ == "__main__":
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "4178"))
    server = ThreadingHTTPServer((host, port), BaselineShareHandler)
    print(f"Baseline Share backend running at http://{host}:{port}")
    server.serve_forever()
