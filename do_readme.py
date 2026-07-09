import subprocess as s
s.run(['git','add','-A'], capture_output=True)
r = s.run(['git','commit','-m','docs: README 补全路线图版本标记'], capture_output=True)
if r.returncode == 0:
    print(r.stdout.decode()[:200])
    s.run(['git','push'])
else:
    print('nothing to commit')