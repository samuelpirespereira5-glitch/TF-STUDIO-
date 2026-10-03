import threading
import uuid

_JOBS = {}
_LOCK = threading.Lock()


def start_job(target, *args, **kwargs):
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "status": "pending", "message": "Iniciando...",
            "result": None, "error": None,
            "elapsed": 0, "estimate": None,
        }

    def runner():
        try:
            result = target(job_id, *args, **kwargs)
            with _LOCK:
                _JOBS[job_id]["status"] = "done"
                _JOBS[job_id]["result"] = result
        except Exception as e:
            with _LOCK:
                _JOBS[job_id]["status"] = "error"
                _JOBS[job_id]["error"] = str(e)

    threading.Thread(target=runner, daemon=True).start()
    return job_id


def set_message(job_id, message):
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["message"] = message


def set_progress(job_id, message, elapsed=None, estimate=None):
    """Como set_message, mas também guarda quanto tempo já passou e uma
    estimativa de duração total — usado para mostrar um cronômetro e
    uma barra de progresso de verdade na tela de criação de site."""

    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["message"] = message
            if elapsed is not None:
                _JOBS[job_id]["elapsed"] = elapsed
            if estimate is not None:
                _JOBS[job_id]["estimate"] = estimate


def get_job(job_id):
    with _LOCK:
        return dict(_JOBS.get(job_id, {}))
