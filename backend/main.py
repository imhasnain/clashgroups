"""
ClashGroups.gg — FastAPI Backend
Run with: uvicorn main:app --reload --port 8000
Docs at:  http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import sqlite3, json, uuid

app = FastAPI(title="ClashGroups.gg API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "clashgroups.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                country TEXT DEFAULT 'Global',
                language TEXT DEFAULT 'English',
                members INTEGER DEFAULT 0,
                invite_link TEXT,
                type TEXT DEFAULT 'Public',
                owner TEXT,
                tags TEXT DEFAULT '[]',
                emoji TEXT DEFAULT '⚔️',
                rating REAL DEFAULT 0,
                views INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                featured INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.commit()

init_db()

# --- Models ---
class GroupCreate(BaseModel):
    name: str
    description: str
    category: str
    country: Optional[str] = "Global"
    language: Optional[str] = "English"
    members: Optional[int] = 0
    invite_link: str
    type: Optional[str] = "Public"
    owner: Optional[str] = "Anonymous"
    tags: Optional[List[str]] = []
    emoji: Optional[str] = "⚔️"

def row_to_dict(row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags", "[]"))
    d["featured"] = bool(d.get("featured", 0))
    return d

# --- Routes ---
@app.get("/")
def root():
    return {"message": "ClashGroups.gg API running", "docs": "/docs"}

@app.get("/groups")
def list_groups(
    search: Optional[str] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    language: Optional[str] = None,
    sort: Optional[str] = "trending",
    limit: int = 20,
    offset: int = 0
):
    query = "SELECT * FROM groups WHERE 1=1"
    params = []
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if category:
        query += " AND category = ?"
        params.append(category)
    if country:
        query += " AND country = ?"
        params.append(country)
    if language:
        query += " AND language = ?"
        params.append(language)

    sort_map = {
        "trending": "views DESC",
        "newest": "created_at DESC",
        "members": "members DESC",
        "rating": "rating DESC",
    }
    query += f" ORDER BY {sort_map.get(sort, 'views DESC')} LIMIT ? OFFSET ?"
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]

@app.get("/groups/{group_id}")
def get_group(group_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM groups WHERE id = ?", [group_id]).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Group not found")
    return row_to_dict(row)

@app.post("/groups", status_code=201)
def create_group(group: GroupCreate):
    gid = str(uuid.uuid4())[:8].upper()
    now = date.today().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO groups
            (id,name,description,category,country,language,members,invite_link,type,owner,tags,emoji,rating,views,clicks,featured,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,0,?)
        """, [gid, group.name, group.description, group.category,
              group.country, group.language, group.members,
              group.invite_link, group.type, group.owner,
              json.dumps(group.tags), group.emoji, now])
        conn.commit()
    return {"id": gid, "message": "Group created successfully"}

@app.post("/groups/{group_id}/view")
def increment_view(group_id: str):
    with get_db() as conn:
        conn.execute("UPDATE groups SET views = views + 1 WHERE id = ?", [group_id])
        conn.commit()
    return {"ok": True}

@app.post("/groups/{group_id}/click")
def increment_click(group_id: str):
    with get_db() as conn:
        conn.execute("UPDATE groups SET clicks = clicks + 1 WHERE id = ?", [group_id])
        conn.commit()
    return {"ok": True}

@app.get("/stats")
def get_stats():
    with get_db() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
        members  = conn.execute("SELECT SUM(members) FROM groups").fetchone()[0] or 0
        countries = conn.execute("SELECT COUNT(DISTINCT country) FROM groups").fetchone()[0]
        cats     = conn.execute("SELECT COUNT(DISTINCT category) FROM groups").fetchone()[0]
    return {"groups": total, "members": members, "countries": countries, "categories": cats}

@app.delete("/groups/{group_id}")
def delete_group(group_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM groups WHERE id = ?", [group_id])
        conn.commit()
    return {"message": "Deleted"}
