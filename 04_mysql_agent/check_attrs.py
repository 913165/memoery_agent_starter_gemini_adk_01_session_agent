import sys
sys.stdout.reconfigure(line_buffering=True)
import os
os.chdir(r'C:\Users\tinum\PycharmProjects\memory_agent_starter_googleai\04_mysql_agent')
from dotenv import load_dotenv
load_dotenv(r'C:\Users\tinum\PycharmProjects\memory_agent_starter_googleai\.env')
from google.adk.sessions import DatabaseSessionService
svc = DatabaseSessionService(db_url='mysql+aiomysql://root:root123@127.0.0.1:3306/adk_sessions')
attrs = [a for a in dir(svc) if not a.startswith('__')]
print("ATTRS:", attrs)
# also check instance dict
print("DICT:", list(svc.__dict__.keys()))

