import subprocess as s
s.run(['git', 'add', '-A'], capture_output=True)
r = s.run(['git', 'commit', '-m', 'feat: complete P0-P5 tasks — VIF test, pytest, dead code cleanup'], capture_output=True)
print(r.stdout.decode()[:200])
s.run(['git', 'push'])