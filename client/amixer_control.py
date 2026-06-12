#!/usr/bin/env python3

import logging
import os
import re
import socket
import subprocess
import threading
import time


SOCKET_PATH = "/tmp/volume_control.sock"

# Configurable ramp settings
RAMP_DURATION_SECONDS = 3
RAMP_STEPS = 10


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


class VolumeController:
    def __init__(self):
        self._stored_volume = None
        self._lock = threading.Lock()

    def get_current_volume(self) -> int:
        logging.info("Getting current volume")

        result = subprocess.run(
            ["amixer", "get", "Speaker"],
            capture_output=True,
            text=True,
            check=True,
        )

        logging.info("amixer output:\n%s", result.stdout)

        match = re.search(
            r"Front Left: Playback (\d+)",
            result.stdout,
        )

        if not match:
            raise RuntimeError(
                "Could not parse Front Left volume from amixer output"
            )

        volume = int(match.group(1))

        logging.info("Parsed current volume: %s", volume)

        return volume

    def set_volume(self, volume: int):
        logging.info("Setting volume to %s", volume)

        result = subprocess.run(
            ["amixer", "set", "Speaker", str(volume)],
            capture_output=True,
            text=True,
            check=True,
        )

        logging.info("amixer set output:\n%s", result.stdout)

    def mute(self):
        logging.info("Handling mute request")

        with self._lock:
            current_volume = self.get_current_volume()
            if current_volume > 0:
                self._stored_volume = current_volume

                logging.info(
                    "Stored volume before mute: %s",
                    self._stored_volume,
                )

                self.set_volume(0)

                logging.info("Speaker muted")
            else:
                logging.info("Speaker already muted")


    def unmute_slowly(
        self,
        duration_seconds: int = RAMP_DURATION_SECONDS,
        steps: int = RAMP_STEPS,
    ):
        logging.info("Handling unmute_slowly request")

        with self._lock:
            target_volume = self._stored_volume

        logging.info("Stored target volume: %s", target_volume)

        if target_volume is None:
            logging.warning("No stored volume available")
            return

        current_volume = self.get_current_volume()

        logging.info("Current volume: %s", current_volume)

        if current_volume >= target_volume:
            logging.info(
                "Current volume already >= target volume"
            )
            return

        volume_difference = target_volume - current_volume
        sleep_time = duration_seconds / steps

        logging.info(
            "Gradually restoring volume over %s seconds in %s steps",
            duration_seconds,
            steps,
        )

        for step in range(1, steps + 1):
            next_volume = current_volume + int(
                (volume_difference * step) / steps
            )

            logging.debug(
                "Step %s/%s: setting volume to %s",
                step,
                steps,
                next_volume,
            )

            self.set_volume(next_volume)

            time.sleep(sleep_time)

        self.set_volume(target_volume)

        logging.info("Finished gradual unmute")


def send_response(conn: socket.socket, value: int):
    response = f"{value}\n"

    logging.info("Sending response: %s", value)

    conn.sendall(response.encode())


def handle_client(
    conn: socket.socket,
    volume_controller: VolumeController,
):
    try:
        data = conn.recv(1024).decode().strip()

        logging.info("Received command: %s", data)

        if data == "mute":
            volume_controller.mute()
            send_response(conn, 200)

        elif data == "unmute_slowly":
            volume_controller.unmute_slowly()
            send_response(conn, 200)

        else:
            logging.warning("Unknown command: %s", data)
            send_response(conn, 400)

    except Exception:
        logging.exception("Error handling client")

        try:
            send_response(conn, 500)
        except Exception:
            logging.exception("Failed sending error response")

    finally:
        logging.info("Closing client connection")

        conn.close()


def create_server_socket(socket_path: str) -> socket.socket:
    if os.path.exists(socket_path):
        logging.info(
            "Removing existing socket file: %s",
            socket_path,
        )
        os.remove(socket_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    server.bind(socket_path)

    server.listen()

    logging.info(
        "Unix socket server listening on %s",
        socket_path,
    )

    return server


def run_server(socket_path: str):
    volume_controller = VolumeController()

    server = create_server_socket(socket_path)

    try:
        while True:
            logging.info("Waiting for client connection")

            conn, _ = server.accept()

            logging.info("Accepted client connection")

            thread = threading.Thread(
                target=handle_client,
                args=(conn, volume_controller),
                daemon=True,
            )

            thread.start()

    finally:
        logging.info("Shutting down server")

        server.close()

        if os.path.exists(socket_path):
            logging.info(
                "Removing socket file: %s",
                socket_path,
            )
            os.remove(socket_path)


if __name__ == "__main__":
    run_server(SOCKET_PATH)
