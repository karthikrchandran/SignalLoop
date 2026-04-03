import sys
sys.path.insert(0, r'c:\Users\K.Ramachandran\eMailVoice\apps\api')
import warnings
warnings.filterwarnings('ignore')

from app.core.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(text('SELECT email, is_active, is_superuser FROM "user" LIMIT 10')).fetchall()
    if rows:
        for r in rows:
            print(f"email={r[0]}, is_active={r[1]}, is_superuser={r[2]}")
    else:
        print("NO USERS FOUND - table is empty")
