import os
import pyodbc
import pymssql
from dotenv import load_dotenv

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER", r".\SQLEXPRESS")
DB_NAME = os.getenv("DB_NAME", "RestoranQRDB")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_TRUSTED = os.getenv("DB_TRUSTED_CONNECTION", "yes").lower() in ("yes", "true", "1")

def get_db_connection():
    """
    MS SQL Server 2022 veritabanına bağlanır.
    """
    errors = []
    
    server_candidates = [DB_SERVER]
    for alt in [r".\SQLEXPRESS", ".", "localhost", r"LOCALHOST\SQLEXPRESS", "127.0.0.1"]:
        if alt not in server_candidates:
            server_candidates.append(alt)

    odbc_drivers = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server"
    ]
    installed_drivers = pyodbc.drivers()
    valid_drivers = [d for d in odbc_drivers if d in installed_drivers]
    if not valid_drivers and installed_drivers:
        valid_drivers = installed_drivers

    for srv in server_candidates:
        for driver in valid_drivers:
            try:
                if DB_TRUSTED or not DB_USER:
                    conn_str = f"DRIVER={{{driver}}};SERVER={srv};DATABASE={DB_NAME};Trusted_Connection=yes;TrustServerCertificate=yes;"
                else:
                    conn_str = f"DRIVER={{{driver}}};SERVER={srv};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASSWORD};TrustServerCertificate=yes;"
                
                conn = pyodbc.connect(conn_str, autocommit=True, timeout=3)
                return conn, f"pyodbc ({srv})"
            except Exception as e:
                errors.append(f"pyodbc ({srv} / {driver}): {str(e)}")

    for srv in server_candidates:
        try:
            if DB_USER and DB_PASSWORD:
                conn = pymssql.connect(server=srv, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, autocommit=True, login_timeout=3)
            else:
                conn = pymssql.connect(server=srv, database=DB_NAME, autocommit=True, login_timeout=3)
            return conn, f"pymssql ({srv})"
        except Exception as e:
            errors.append(f"pymssql ({srv}): {str(e)}")

    raise Exception("MS SQL Server 2022 veritabanına bağlanılamadı. Hatalar:\n" + "\n".join(errors[:5]))

def execute_query(query, params=(), fetch_all=True, fetch_one=False):
    """
    SQL Sorgusu çalıştırır ve dict formatında sonuç döner.
    """
    conn, driver_type = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)

        if cursor.description is None:
            conn.close()
            return None

        columns = [column[0] for column in cursor.description]
        
        if fetch_one:
            row = cursor.fetchone()
            conn.close()
            if row:
                return dict(zip(columns, row))
            return None
        
        if fetch_all:
            rows = cursor.fetchall()
            conn.close()
            return [dict(zip(columns, row)) for row in rows]

        conn.close()
        return None
    except Exception as e:
        conn.close()
        raise e

def execute_non_query(query, params=()):
    """
    INSERT, UPDATE, DELETE sorguları çalıştırır.
    """
    conn, driver_type = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        inserted_id = None
        try:
            cursor.execute("SELECT SCOPE_IDENTITY()")
            row = cursor.fetchone()
            if row and row[0] is not None:
                inserted_id = int(row[0])
        except Exception:
            pass

        conn.close()
        return inserted_id
    except Exception as e:
        conn.close()
        raise e
