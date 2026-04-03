import sys
sys.path.insert(0, r'c:\Users\K.Ramachandran\eMailVoice\apps\api')
import warnings
warnings.filterwarnings('ignore')

from sqlmodel import Session
from app.core.db import engine, init_db

with Session(engine) as session:
    init_db(session)
    session.commit()
    print("Superuser seeded successfully.")
