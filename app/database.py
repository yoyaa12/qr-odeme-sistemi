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

_cached_conn_params = None
import contextvars
from contextlib import contextmanager

_transaction_conn = contextvars.ContextVar('transaction_conn', default=None)

@contextmanager
def db_transaction():
    """
    Tüm veritabanı işlemlerini tek bir işlem bloğu (transaction) içerisine alır.
    Hata durumunda rollback yapar, başarılıysa commit eder.
    """
    if _transaction_conn.get():
        yield _transaction_conn.get()
        return

    conn, _ = get_db_connection(autocommit=False)
    token = _transaction_conn.set(conn)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        _transaction_conn.reset(token)
        conn.close()

def get_db_connection(autocommit=True):
    """
    MS SQL Server 2022 veritabanına bağlanır (Performans için önbellekli).
    """
    global _cached_conn_params
    errors = []

    # 1. Önceden başarıyla çalışan parametre varsa hızlıca bağlan
    if _cached_conn_params:
        try:
            c_type, srv, driver = _cached_conn_params
            if c_type == 'pyodbc':
                if DB_TRUSTED or not DB_USER:
                    conn_str = f"DRIVER={{{driver}}};SERVER={srv};DATABASE={DB_NAME};Trusted_Connection=yes;TrustServerCertificate=yes;"
                else:
                    conn_str = f"DRIVER={{{driver}}};SERVER={srv};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASSWORD};TrustServerCertificate=yes;"
                conn = pyodbc.connect(conn_str, autocommit=autocommit, timeout=2)
                return conn, f"pyodbc ({srv})"
            elif c_type == 'pymssql':
                if DB_USER and DB_PASSWORD:
                    conn = pymssql.connect(server=srv, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, autocommit=autocommit, login_timeout=2)
                else:
                    conn = pymssql.connect(server=srv, database=DB_NAME, autocommit=autocommit, login_timeout=2)
                return conn, f"pymssql ({srv})"
        except Exception:
            _cached_conn_params = None # Bağlantı koptuysa önbelleği sıfırla

    # 2. Önbellek yoksa veya sıfırlandıysa adayları hızlıca tara
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
                
                conn = pyodbc.connect(conn_str, autocommit=autocommit, timeout=2)
                _cached_conn_params = ('pyodbc', srv, driver)
                return conn, f"pyodbc ({srv})"
            except Exception as e:
                errors.append(f"pyodbc ({srv} / {driver}): {str(e)}")

    for srv in server_candidates:
        try:
            if DB_USER and DB_PASSWORD:
                conn = pymssql.connect(server=srv, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, autocommit=autocommit, login_timeout=2)
            else:
                conn = pymssql.connect(server=srv, database=DB_NAME, autocommit=autocommit, login_timeout=2)
            _cached_conn_params = ('pymssql', srv, None)
            return conn, f"pymssql ({srv})"
        except Exception as e:
            errors.append(f"pymssql ({srv}): {str(e)}")

    raise Exception("MS SQL Server 2022 veritabanına bağlanılamadı. Hatalar:\n" + "\n".join(errors[:5]))

def execute_query(query, params=(), fetch_all=True, fetch_one=False):
    """
    SQL Sorgusu çalıştırır ve dict formatında sonuç döner.
    """
    t_conn = _transaction_conn.get()
    close_after = False
    
    if t_conn:
        conn = t_conn
    else:
        conn, driver_type = get_db_connection()
        close_after = True

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)

        if cursor.description is None:
            return None

        columns = [column[0] for column in cursor.description]
        
        if fetch_one:
            row = cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None
        
        if fetch_all:
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

        return None
    finally:
        if cursor:
            cursor.close()
        if close_after:
            conn.close()

def execute_non_query(query, params=()):
    """
    INSERT, UPDATE, DELETE sorguları çalıştırır.
    """
    t_conn = _transaction_conn.get()
    close_after = False
    
    if t_conn:
        conn = t_conn
    else:
        conn, driver_type = get_db_connection()
        close_after = True

    cursor = None
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

        return inserted_id
    finally:
        if cursor:
            cursor.close()
        if close_after:
            conn.close()

class DatabaseSession:
    """Dependency Injection için veritabanı oturum arayüzü"""
    def execute_query(self, query, params=(), fetch_all=True, fetch_one=False):
        return execute_query(query, params, fetch_all, fetch_one)
        
    def execute_non_query(self, query, params=()):
        return execute_non_query(query, params)

def get_db():
    """FastAPI endpointleri ve repository'ler için DB dependency'si"""
    db = DatabaseSession()
    try:
        yield db
    finally:
        pass
