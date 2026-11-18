from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3, secrets, hashlib

DB = Path(__file__).resolve().parents[1] / "gatepass.db"
app = FastAPI(title="Apartment Visitor & Delivery Gatepass", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def stamp():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS flats(id INTEGER PRIMARY KEY, block_name TEXT NOT NULL, flat_number TEXT NOT NULL, UNIQUE(block_name,flat_number));
        CREATE TABLE IF NOT EXISTS residents(id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, phone TEXT, flat_id INTEGER NOT NULL REFERENCES flats(id));
        CREATE TABLE IF NOT EXISTS security_staff(id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, staff_code TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS delivery_agents(id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, phone TEXT, company TEXT);
        CREATE TABLE IF NOT EXISTS gatepasses(
          id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_name TEXT NOT NULL, visitor_phone TEXT,
          visit_type TEXT NOT NULL CHECK(visit_type IN ('visitor','delivery')), purpose TEXT,
          company TEXT, vehicle_number TEXT, flat_id INTEGER NOT NULL REFERENCES flats(id),
          resident_id INTEGER NOT NULL REFERENCES residents(id), status TEXT NOT NULL DEFAULT 'pending',
          otp_hash TEXT, otp_expires_at TEXT, demo_otp TEXT, created_at TEXT NOT NULL,
          decided_at TEXT, checked_in_at TEXT, checked_out_at TEXT
        );
        CREATE TABLE IF NOT EXISTS visitor_logs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, gatepass_id INTEGER NOT NULL REFERENCES gatepasses(id),
          event_type TEXT NOT NULL, event_time TEXT NOT NULL, notes TEXT
        );
        """)
        if c.execute("SELECT COUNT(*) FROM flats").fetchone()[0] == 0:
            c.executemany("INSERT INTO flats(block_name,flat_number) VALUES(?,?)",[("A Block","101"),("A Block","102"),("B Block","201"),("B Block","202")])
            c.execute("INSERT INTO residents(full_name,phone,flat_id) VALUES(?,?,?)",("Demo Resident","9000000001",1))
            c.execute("INSERT INTO residents(full_name,phone,flat_id) VALUES(?,?,?)",("Arun Kumar","9000000003",2))
            c.execute("INSERT INTO residents(full_name,phone,flat_id) VALUES(?,?,?)",("Priya Sharma","9000000004",3))
            c.execute("INSERT INTO security_staff(full_name,staff_code) VALUES(?,?)",("Demo Security","SEC001"))

init_db()

class GatepassIn(BaseModel):
    visitor_name: str = Field(min_length=2, max_length=100)
    visitor_phone: Optional[str] = None
    visit_type: str
    purpose: Optional[str] = None
    company: Optional[str] = None
    vehicle_number: Optional[str] = None
    flat_id: int
    resident_id: int

class DecisionIn(BaseModel):
    decision: str
    resident_id: int

class OTPIn(BaseModel):
    otp: str = Field(min_length=6, max_length=6)

@app.get("/")
def home():
    return {"app":"Apartment Visitor & Delivery Gatepass","status":"running","docs":"/docs"}

@app.get("/api/health")
def health():
    return {"status":"ok"}

@app.get("/api/flats")
def flats():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM flats ORDER BY block_name,flat_number")]

@app.get("/api/residents")
def residents():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM residents ORDER BY full_name")]

@app.get("/api/gatepasses")
def gatepasses():
    with conn() as c:
        rows = c.execute("""SELECT g.*, f.block_name, f.flat_number, r.full_name AS resident_name
          FROM gatepasses g JOIN flats f ON f.id=g.flat_id JOIN residents r ON r.id=g.resident_id
          ORDER BY g.id DESC LIMIT 200""").fetchall()
        return [dict(r) for r in rows]

@app.get("/api/visitor-logs")
def logs():
    with conn() as c:
        return [dict(r) for r in c.execute("""SELECT l.*,g.visitor_name,g.visit_type,f.block_name,f.flat_number
          FROM visitor_logs l JOIN gatepasses g ON g.id=l.gatepass_id JOIN flats f ON f.id=g.flat_id
          ORDER BY l.id DESC LIMIT 300""")]

@app.post("/api/gatepasses", status_code=201)
def create_gatepass(p: GatepassIn):
    if p.visit_type not in ("visitor","delivery"):
        raise HTTPException(400,"Choose visitor or delivery.")
    with conn() as c:
        resident = c.execute("SELECT * FROM residents WHERE id=?",(p.resident_id,)).fetchone()
        flat = c.execute("SELECT * FROM flats WHERE id=?",(p.flat_id,)).fetchone()
        if not resident or not flat: raise HTTPException(404,"Flat or resident not found.")
        if resident["flat_id"] != p.flat_id: raise HTTPException(400,"Resident does not belong to the selected flat.")
        cur = c.execute("""INSERT INTO gatepasses(visitor_name,visitor_phone,visit_type,purpose,company,vehicle_number,flat_id,resident_id,created_at)
          VALUES(?,?,?,?,?,?,?,?,?)""",(p.visitor_name,p.visitor_phone,p.visit_type,p.purpose,p.company,p.vehicle_number,p.flat_id,p.resident_id,stamp()))
        return {"id":cur.lastrowid,"message":"Approval request sent."}

@app.post("/api/gatepasses/{gid}/decision")
def decision(gid: int, p: DecisionIn):
    if p.decision not in ("approve","reject"): raise HTTPException(400,"Decision must be approve or reject.")
    with conn() as c:
        row = c.execute("SELECT * FROM gatepasses WHERE id=?",(gid,)).fetchone()
        if not row: raise HTTPException(404,"Gatepass not found.")
        if row["resident_id"] != p.resident_id: raise HTTPException(403,"This request belongs to another resident.")
        if row["status"] != "pending": raise HTTPException(409,"This request has already been processed.")
        if p.decision == "reject":
            c.execute("UPDATE gatepasses SET status='rejected',decided_at=? WHERE id=?",(stamp(),gid))
            return {"status":"rejected"}
        otp = f"{secrets.randbelow(1000000):06d}"
        expiry = (datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
        c.execute("UPDATE gatepasses SET status='approved',otp_hash=?,otp_expires_at=?,demo_otp=?,decided_at=? WHERE id=?",
                  (hashlib.sha256(otp.encode()).hexdigest(),expiry,otp,stamp(),gid))
        return {"status":"approved","demo_otp":otp,"expires_in_minutes":10}

@app.post("/api/gatepasses/{gid}/verify-otp")
def verify(gid: int, p: OTPIn):
    with conn() as c:
        row = c.execute("SELECT * FROM gatepasses WHERE id=?",(gid,)).fetchone()
        if not row: raise HTTPException(404,"Gatepass not found.")
        if row["status"] != "approved": raise HTTPException(409,"Only approved requests can be checked in.")
        expiry = datetime.fromisoformat(row["otp_expires_at"])
        if datetime.now(timezone.utc) > expiry:
            c.execute("UPDATE gatepasses SET status='expired',demo_otp=NULL WHERE id=?",(gid,))
            raise HTTPException(400,"OTP expired. Create a new gatepass request.")
        if not secrets.compare_digest(hashlib.sha256(p.otp.encode()).hexdigest(),row["otp_hash"]):
            raise HTTPException(400,"Incorrect OTP. Please try again.")
        c.execute("UPDATE gatepasses SET status='checked_in',checked_in_at=?,demo_otp=NULL WHERE id=?",(stamp(),gid))
        c.execute("INSERT INTO visitor_logs(gatepass_id,event_type,event_time) VALUES(?,?,?)",(gid,"entry",stamp()))
        return {"status":"checked_in","message":"OTP verified. Entry recorded."}

@app.post("/api/gatepasses/{gid}/checkout")
def checkout(gid: int):
    with conn() as c:
        row = c.execute("SELECT * FROM gatepasses WHERE id=?",(gid,)).fetchone()
        if not row: raise HTTPException(404,"Gatepass not found.")
        if row["status"] != "checked_in": raise HTTPException(409,"Only checked-in visitors can check out.")
        c.execute("UPDATE gatepasses SET status='checked_out',checked_out_at=? WHERE id=?",(stamp(),gid))
        c.execute("INSERT INTO visitor_logs(gatepass_id,event_type,event_time) VALUES(?,?,?)",(gid,"exit",stamp()))
        return {"status":"checked_out","message":"Exit recorded."}
