import json,sqlite3,time
from pathlib import Path
class Store:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.file=self.root/'studio.sqlite3'
        with self.connect() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT,spec TEXT,status TEXT,created REAL,pid INTEGER,result TEXT);
            CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY,path TEXT UNIQUE,parent TEXT,run TEXT,step INTEGER,bytes INTEGER,modified REAL,label TEXT DEFAULT '',collection TEXT DEFAULT '',pinned INTEGER DEFAULT 0,deleted INTEGER DEFAULT 0,job TEXT);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at REAL,action TEXT,details TEXT);
            CREATE TABLE IF NOT EXISTS telemetry(at REAL PRIMARY KEY,data TEXT);
            CREATE TABLE IF NOT EXISTS presets(name TEXT PRIMARY KEY,spec TEXT);''')
    def connect(self):
        db=sqlite3.connect(self.file,timeout=10);db.row_factory=sqlite3.Row;return db
    def rows(self,sql,args=()):
        with self.connect() as db:return [dict(r) for r in db.execute(sql,args)]
    def write(self,sql,args=()):
        with self.connect() as db:db.execute(sql,args)
    def audit(self,action,details):self.write('INSERT INTO audit(at,action,details) VALUES(?,?,?)',(time.time(),action,json.dumps(details)))
    def jobs(self):
        rows=self.rows('SELECT * FROM jobs ORDER BY created DESC LIMIT 500')
        for row in rows:
            row['spec']=json.loads(row['spec']);row['result']=json.loads(row['result'] or '{}')
        return rows
