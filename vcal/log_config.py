import logging
import os

# Optional: Enable low-level debugging to see raw HTTP headers/body


def setup_logging(level=int|str, log_file=None, stdout=True, http_debug=None):
    handlers = []
    log_level = level if isinstance(level, int) else getattr(logging, str(level).upper(), logging.INFO)


    if log_file:
        handlers.append(logging.FileHandler(log_file))

    if stdout:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )

    if http_debug is not None:
        import http.client
        http.client.HTTPConnection.debuglevel = http_debug



# Always send server logs to file
def setup_logging_for_http_server(level):
    setup_logging(level=level, log_file="logs/server.log", stdout=True)

def setup_logging_for_alarms(level, http_debug=None):
    setup_logging(level=level, log_file="logs/alarms.log" if is_cron() else None, stdout=not is_cron(), http_debug=http_debug)

def setup_logging_for_announcements(level, http_debug=None):
    setup_logging(level=level, log_file="logs/announcements.log" if is_cron() else None, stdout=not is_cron(), http_debug=http_debug)

def setup_logging_for_data_refresh(level, http_debug=None):
    setup_logging(level=level, log_file="logs/data_refresh.log" if is_cron() else None, stdout=not is_cron(), http_debug=http_debug)

# If IS_CRON=true environment variable is set, log to a file instead of stdout
def is_cron():
    return os.getenv("IS_CRON", "false").lower() == "true"