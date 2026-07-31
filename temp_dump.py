from app.database import get_db_connection
import json

try:
    conn, driver = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, masa_no FROM Masalar")
    masalar = cursor.fetchall()
    
    cursor.execute("SELECT id, masa_id, siparis_durumu FROM Siparisler")
    sip = cursor.fetchall()
    
    with open('dump_out.txt', 'w') as f:
        f.write("MASALAR: " + json.dumps([[r[0], r[1]] for r in masalar]) + "\n")
        f.write("SIPARISLER: " + json.dumps([[r[0], r[1], r[2]] for r in sip]) + "\n")
    
    conn.close()
except Exception as e:
    with open('dump_out.txt', 'w') as f:
        f.write("ERROR: " + str(e))
