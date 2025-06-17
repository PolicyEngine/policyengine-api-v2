import time
from functools import wraps
from policyengine_simulation_api_client.exceptions import ServiceException

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 2


def retry_on_503(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except ServiceException as e:
                # if e.http_resp.status == 503:
                status_code = getattr(e, "http_resp", None)
                if status_code and status_code.status == 503:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue
                    else:
                        raise RuntimeError(
                            f"{func.__name__} failed after {MAX_RETRIES} retries (503)"
                        )
                else:
                    raise  # Re-raise other status codes

    return wrapper
