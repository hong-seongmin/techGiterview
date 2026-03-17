#!/usr/bin/env python3
"""
Database Tables Creation Script

SQLAlchemy 모델을 기반으로 데이터베이스 테이블 생성
"""

from app.core.database import engine, Base
import app.models  # noqa: F401
from app.models.repository import RepositoryAnalysis, AnalyzedFile
from app.models.interview import InterviewSession
from app.models.user import User

def create_tables():
    """모든 테이블 생성"""
    print("[CREATE] Creating database tables...")
    
    try:
        # 모든 테이블 생성
        Base.metadata.create_all(bind=engine)
        print("[SUCCESS] Database tables created successfully!")
        
        # 생성된 테이블 목록 출력
        print("\n[INFO] Created tables:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
            
    except Exception as e:
        print(f"[ERROR] Error creating tables: {e}")
        raise

def drop_tables():
    """모든 테이블 삭제 (개발용)"""
    print("[DROP] Dropping all database tables...")
    
    try:
        Base.metadata.drop_all(bind=engine)
        print("[SUCCESS] All tables dropped successfully!")
    except Exception as e:
        print(f"[ERROR] Error dropping tables: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        drop_tables()
        create_tables()
    else:
        create_tables()
