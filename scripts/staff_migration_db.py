"""Exact-target SQL Server connection used only by staff migration tooling."""

from __future__ import annotations

import pyodbc

from app.database import DB_NAME, DB_PASSWORD, DB_SERVER, DB_TRUSTED, DB_USER


_DRIVER_PREFERENCE = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


def get_strict_migration_connection(*, autocommit: bool):
    """Connect only to configured DB_SERVER; never scan alternative instances."""

    installed = set(pyodbc.drivers())
    drivers = [driver for driver in _DRIVER_PREFERENCE if driver in installed]
    if not drivers:
        raise RuntimeError("No supported SQL Server ODBC driver is installed")

    connection = None
    for driver in drivers:
        if DB_TRUSTED or not DB_USER:
            connection_string = (
                f"DRIVER={{{driver}}};SERVER={DB_SERVER};DATABASE={DB_NAME};"
                "Trusted_Connection=yes;TrustServerCertificate=yes;"
            )
        else:
            connection_string = (
                f"DRIVER={{{driver}}};SERVER={DB_SERVER};DATABASE={DB_NAME};"
                f"UID={DB_USER};PWD={DB_PASSWORD};TrustServerCertificate=yes;"
            )
        try:
            connection = pyodbc.connect(
                connection_string,
                autocommit=autocommit,
                timeout=5,
            )
            break
        except pyodbc.Error:
            connection = None
    if connection is None:
        raise RuntimeError("Configured SQL Server target is unavailable")

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT DB_NAME(), CONVERT(nvarchar(128), SERVERPROPERTY('ServerName'))"
        )
        row = cursor.fetchone()
        if not row or str(row[0]).casefold() != DB_NAME.casefold():
            raise RuntimeError("Connected database does not match DB_NAME")
        server_identity = str(row[1])
    except Exception:
        connection.close()
        raise
    finally:
        if cursor is not None:
            cursor.close()
    return connection, server_identity
