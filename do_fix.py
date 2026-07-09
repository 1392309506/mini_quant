import subprocess
r = subprocess.run(['git', 'add', '-A'], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'fix: run_simulation.py typo + NLV calc'], capture_output=True)
print(r.stdout.decode()[:300])
r = subprocess.run(['git', 'push'], capture_output=True)
print(r.stdout.decode()[:300])