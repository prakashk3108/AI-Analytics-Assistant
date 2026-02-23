import os, msal, pyodbc

env_path = r"C:\Users\PrakashKaliyaperumal\Documents\AI work\sqlfromllm\.env"
with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k] = v

tenant = os.environ["FABRIC_TENANT_ID"]
client_id = os.environ["FABRIC_CLIENT_ID"]
client_secret = os.environ["FABRIC_CLIENT_SECRET"]
server = os.environ["FABRIC_SQL_ENDPOINT"]
database = os.environ["FABRIC_DATABASE"]

conn = pyodbc.connect(
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server=tcp:{server},1433;"
    f"Database={database};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Authentication=ActiveDirectoryServicePrincipal;"
    f"UID={client_id};"
    f"PWD={client_secret};"
    f"Authority Id={tenant};"
)
cur = conn.cursor()
cur.execute("SELECT 1")
print(cur.fetchone())
conn.close()
