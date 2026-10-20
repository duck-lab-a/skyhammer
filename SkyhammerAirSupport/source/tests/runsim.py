import sys, runpy, os
sys.path.insert(0, r'C:\Users\user\Documents\Codex\2026-09-30\w\work\lua-test-runtime')
t = sys.argv[1]; sys.argv = [t]
os.chdir(os.path.dirname(os.path.abspath(t)))
sys.path.insert(0, os.path.dirname(os.path.abspath(t)))
runpy.run_path(t, run_name='__main__')
