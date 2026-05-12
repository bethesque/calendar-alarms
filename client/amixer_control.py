#!/usr/bin/env python3

import os
import re
import socket
import subprocess
import threading
import time


SOCKET_PATH = "/tmp/volume_control.sock"

# Configurable ramp settings
RAMP_DURATION_SECONDS = 5
RAMP_STEPS = 10


class VolumeController:
    def __init__(self):
        self._stored_volume = None
        self._lock = threading.Lock()

    def get_current_volume(self) -> int:
        result = self.run_subprocess(
            ["amixer", "get", "Speaker"],
            capture_output=True,
            text=True,
            check=True,
        )

        match = re.search(
            r"Front Left: Playback (\d+)",
            result.stdout,
        )

        if not match:
            raise RuntimeError("Could not parse Front Left volume")

        return int(match.group(1))

    def set_volume(self, volume: int):
        subprocess.run(
            ["amixer", "set", "Speaker", str(volume)],
            check=True,
        )

    def mute(self):
        with self._lock:
            current_volume = self.get_current_volume()
            self._stored_volume = current_volume

        self.set_volume(0)

    def unmute_slowly(
        self,
        duration_seconds: int = RAMP_DURATION_SECONDS,
        steps: int = RAMP_STEPS,
    ):
        with self._lock:
            target_volume = self._stored_volume

        if target_volume is None:
            return

        current_volume = self.get_current_volume()

        if current_volume >= target_volume:
            return

        volume_difference = target_volume - current_volume
        sleep_time = duration_seconds / steps

        for step in range(1, steps + 1):
            next_volume = current_volume + int(
                (volume_difference * step) / steps
            )

            self.set_volume(next_volume)
            time.sleep(sleep_time)

        self.set_volume(target_volume)

    def run_subprocess(*args, **kwargs):
        return subprocess.run(*args, **kwargs)



def send_response(conn: socket.socket, value: int):
    conn.sendall(f"{value}\n".encode())


def handle_client(conn: socket.socket, volume_controller: VolumeController):
    try:
        data = conn.recv(1024).decode().strip()

        if data == "mute":
            send_response(conn, 200)
            volume_controller.mute()

        elif data == "unmute_slowly":
            send_response(conn, 200)
            volume_controller.unmute_slowly()

        else:
            send_response(conn, 400)

    except Exception as e:
        print(f"Error handling client: {e}")

        try:
            send_response(conn, 500)
        except Exception:
            pass

    finally:
        conn.close()


def create_server_socket(socket_path: str) -> socket.socket:
    if os.path.exists(socket_path):
        os.remove(socket_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen()

    return server


def run_server(socket_path: str):
    volume_controller = VolumeController()
    server = create_server_socket(socket_path)

    print(f"Listening on unix socket: {socket_path}")

    try:
        while True:
            conn, _ = server.accept()

            thread = threading.Thread(
                target=handle_client,
                args=(conn, volume_controller),
                daemon=True,
            )
            thread.start()

    finally:
        server.close()

        if os.path.exists(socket_path):
            os.remove(socket_path)


if __name__ == "__main__":
    run_server(SOCKET_PATH)