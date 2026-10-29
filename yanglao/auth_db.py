# -*- coding: utf-8 -*-
"""用户注册/登录与登录会话,存本地 SQLite(data.db),零第三方依赖。

密码用 pbkdf2_hmac 加盐哈希,不存明文;登录令牌随机生成,存 sessions 表。
"""
import hashlib
import os
import secrets
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def init():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          phone TEXT DEFAULT '',
          pwd_hash TEXT NOT NULL,
          pwd_salt TEXT NOT NULL,
          region TEXT DEFAULT '',
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions(
          token TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          created_at INTEGER NOT NULL
        );
        """)


def _hash(pwd, salt):
    return hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt.encode("utf-8"), 120000).hex()


def create_user(username, password, phone="", region=""):
    """成功返回用户 id;用户名已存在返回 None。"""
    salt = secrets.token_hex(16)
    try:
        with _conn() as con:
            cur = con.execute(
                "INSERT INTO users(username, phone, pwd_hash, pwd_salt, region, created_at)"
                " VALUES(?,?,?,?,?,?)",
                (username, phone, _hash(password, salt), salt, region, int(time.time())))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def user_exists(username):
    with _conn() as con:
        return con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone() is not None


def check_login(username, password):
    """密码对返回用户 id,否则 None。"""
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or _hash(password, row["pwd_salt"]) != row["pwd_hash"]:
        return None
    return row["id"]


def new_session(user_id):
    token = secrets.token_hex(32)
    with _conn() as con:
        con.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)",
                    (token, user_id, int(time.time())))
    return token


def get_user_by_token(token):
    if not token:
        return None
    with _conn() as con:
        row = con.execute(
            "SELECT u.id, u.username, u.phone, u.region, u.created_at"
            " FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,)).fetchone()
    return dict(row) if row else None


def drop_session(token):
    with _conn() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))


def set_region(user_id, region):
    with _conn() as con:
        con.execute("UPDATE users SET region=? WHERE id=?", (region, user_id))


init()
