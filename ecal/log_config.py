import logging
import os

def setup_logging(level=logging.INFO, log_file=None, stdout=True):
    handlers = []

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    if stdout:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )

# Always send server logs to file
def setup_logging_for_http_server(level=logging.INFO):
    setup_logging(level=level, log_file="logs/server.log", stdout=True)

def setup_logging_for_alarms(level=logging.INFO):
    setup_logging(level=level, log_file="logs/alarms.log" if is_cron() else None, stdout=not is_cron())

def setup_logging_for_announcements(level=logging.INFO):
    setup_logging(level=level, log_file="logs/announcements.log" if is_cron() else None, stdout=not is_cron())

def setup_logging_for_data_refresh(level=logging.INFO):
    setup_logging(level=level, log_file="logs/data_refresh.log" if is_cron() else None, stdout=not is_cron())

# If IS_CRON=true environment variable is set, log to a file instead of stdout
def is_cron():
    return os.getenv("IS_CRON", "false").lower() == "true"