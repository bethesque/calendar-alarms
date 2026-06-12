import logging
from venv import logger

from vcal.scene import Scene


if __name__ == "__main__":

    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    scene = Scene()
    scene.save()
    scene.prepare_for_alarm()
    input("Press Enter to restore after alarm...")
    scene.restore_after_alarm()