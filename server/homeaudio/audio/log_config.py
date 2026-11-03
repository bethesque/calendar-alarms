import logging
import os

# Optional: Enable low-level debugging to see raw HTTP headers/body


def setup_logging(level=int|str, http_debug=None):
    handlers = []
    log_level = level if isinstance(level, int) else getattr(logging, str(level).upper(), logging.INFO)

    handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )

    if http_debug is not None:
        import http.client
        http.client.HTTPConnection.debuglevel = http_debug
