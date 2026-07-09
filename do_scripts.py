import subprocess as s
s.run(['git','add','-A'], capture_output=True)
s.run(['git','commit','-m','docs: scripts/README.md add run_simulation.py section'], capture_output=True)
s.run(['git','push'])