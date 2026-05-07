Set-Location C:\Users\K.Ramachandran\eMailVoice\apps\api
& C:\Users\K.Ramachandran\eMailVoice\.venv\Scripts\python.exe -m coverage run --source=app.initial_data,app.core.idempotency,app.workers.postcall_worker -m pytest tests/scripts/test_initial_data.py tests/unit/test_idempotency.py tests/workers/test_postcall_worker.py -q
& C:\Users\K.Ramachandran\eMailVoice\.venv\Scripts\python.exe -m coverage report
