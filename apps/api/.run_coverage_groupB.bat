@echo off
cd /d C:\Users\K.Ramachandran\eMailVoice\apps\api
C:\Users\K.Ramachandran\eMailVoice\.venv\Scripts\python.exe -m coverage run --data-file=.cov_groupB --source=app.workers.call_worker,app.workers.sequence_worker -m pytest tests/workers/test_call_worker.py tests/workers/test_sequence_worker.py -q > C:\Users\K.Ramachandran\eMailVoice\apps\api\.cov_run.txt 2>&1
C:\Users\K.Ramachandran\eMailVoice\.venv\Scripts\python.exe -m coverage report --data-file=.cov_groupB > C:\Users\K.Ramachandran\eMailVoice\apps\api\.cov_report.txt 2>&1
