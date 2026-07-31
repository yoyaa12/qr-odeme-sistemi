from app.database import get_db_connection

def setup_db():
    conn, _ = get_db_connection()
    cursor = conn.cursor()
    
    # Add device_id to Siparisler if not exists
    try:
        cursor.execute("ALTER TABLE Siparisler ADD device_id VARCHAR(100) NULL")
        print("Added device_id to Siparisler")
    except Exception as e:
        print("Siparisler.device_id might already exist:", e)
        
    # Create BannedDevices table
    try:
        cursor.execute("""
        CREATE TABLE BannedDevices (
            id INT IDENTITY(1,1) PRIMARY KEY,
            device_id VARCHAR(100) NOT NULL UNIQUE,
            banned_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("Created BannedDevices table")
    except Exception as e:
        print("BannedDevices might already exist:", e)
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_db()
