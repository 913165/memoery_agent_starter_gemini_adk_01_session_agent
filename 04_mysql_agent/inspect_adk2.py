from google.adk.sessions import DatabaseSessionService
import inspect, sys

src = inspect.getsource(DatabaseSessionService)

with open(r'C:\Users\tinum\AppData\Local\Temp\adk_full.txt', 'w', encoding='utf-8') as f:
    f.write(src)

# print lines with v0/v1/schema/pickle/version/legacy/migrate keywords
keywords = ['v0', 'v1', 'schema', 'pickle', 'version', 'legacy', 'migrate',
            'LargeBinary', 'BLOB', 'blob', 'actions', 'create_all', 'metadata']
for i, line in enumerate(src.split('\n')):
    if any(k in line for k in keywords):
        print(f"{i:4d}: {line}")

