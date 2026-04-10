import subprocess
r = subprocess.run(['docker', 'ps', '-a'], capture_output=True, text=True)
print("STDOUT:", repr(r.stdout))
print("STDERR:", repr(r.stderr))
print("CODE:", r.returncode)

