from google.adk.sessions import DatabaseSessionService
import inspect

src = inspect.getsource(DatabaseSessionService)
lines = src.split('\n')
keywords = ['create_all', 'metadata', 'Column', 'Table', 'schema_version',
            'v0', 'v1', 'pickle', 'Pickle', 'actions', 'BLOB', 'LargeBinary',
            'JSON', 'migrate', 'legacy']

with open(r'C:\Users\tinum\AppData\Local\Temp\adk_src.txt', 'w') as f:
    for i, l in enumerate(lines):
        if any(k in l for k in keywords):
            f.write(f'{i}: {l}\n')

    f.write('\n\n--- FULL SOURCE ---\n')
    f.write(src)

print("Done. Written to temp file.")

