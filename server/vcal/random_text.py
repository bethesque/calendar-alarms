import random
import os
from collections import Counter
import logging
from vcal.env import CACHE_DIRECTORY, RESOURCES_DIRECTORY
from typing import Protocol

logger = logging.getLogger(__name__)

CHOICE_HISTORY_DIR = CACHE_DIRECTORY + "/random_text_selection_history"

"""
threshold is the probability of returning the randomly selected text instead of the default text.
For example, if threshold is 0.3, then there is a 30% chance of returning the randomly selected text and a 70% chance of returning the default text.
"""


class OptionsSource(Protocol):
    def get_choices(self) -> list[str]:
        ...

    def get_name(self) -> str:
        ...

class TextFileOptionsSource:
    def __init__(self, file_name: str, resources_directory=RESOURCES_DIRECTORY):
        self.file_name = file_name
        self.resources_directory = resources_directory
        self.text_options_full_path = os.path.join(self.resources_directory, self.file_name)
        self.name = os.path.splitext(self.file_name)[0]

    def get_choices(self) -> list[str]:
        if not os.path.exists(self.text_options_full_path):
            logger.warning(f"{self.text_options_full_path} file not found. Cannot provide options for random choice. Returning empty list.")
            return []
        with open(self.text_options_full_path, "r", encoding="utf-8") as fa:
            return [line.rstrip("\n") for line in fa]

    def get_name(self) -> str:
        return self.name

    def __str__(self):
        return f"Text file options source {self.text_options_full_path}"


class FileListOptionsSource:
    def __init__(self, directory: str, extensions: list[str] | None = None):
        self.directory = directory
        self.extensions = extensions
        self.name = os.path.basename(directory)

    def get_choices(self) -> list[str]:
        if not os.path.exists(self.directory):
            logger.warning(f"{self.directory} does not exist. Cannot provide options for random choice. Returning empty list.")
            return []
        files = [os.path.abspath(os.path.join(self.directory, f)) for f in os.listdir(self.directory)]
        files = [f for f in files if os.path.isfile(os.path.join(self.directory, f))]
        if self.extensions:
            files = [f for f in files if any(f.endswith(ext) for ext in self.extensions)]
        return files

    def get_name(self) -> str:
        return self.name

    def __str__(self):
        return f"File list options source {self.directory}"

def select_text(default_text: str | None,
                         threshold: float,
                         options_source: OptionsSource,
                         choice_history_dir = CHOICE_HISTORY_DIR) -> str | None:
    """
    - Generate a random float in [0, 1)
    - If rand_val > threshold:
        - Pick an option from options_source (multiset-aware, excluding selection_history)
        - Append it to selection_history
        - Return the chosen line
    - Else:
        - Return default_text
    """


    selection_history = os.path.join(choice_history_dir, os.path.splitext(options_source.get_name())[0] + "_history.txt")

    logger.debug(f"Randomly selecting text from {options_source}, excluding recent choices in {selection_history}")

    rand_val = random.random()

    if rand_val > threshold:
        logger.debug(f"Random value {rand_val:.4f} is greater than threshold {threshold}, returning default text: {default_text}")
        return default_text

    lines_a = options_source.get_choices()

    if not lines_a:
        logger.debug(f"{options_source} is empty. Returning default text.")
        return default_text

    counter_a = Counter(lines_a)

    # Read selection_history (optional)
    try:
        with open(selection_history, "r", encoding="utf-8") as fb:
            lines_b = [line.rstrip("\n") for line in fb]
        counter_b = Counter(lines_b)
    except FileNotFoundError:
        counter_b = Counter()

    remaining_counter = counter_a - counter_b

    if not remaining_counter:
        # Reset selection_history
        open(selection_history, "w", encoding="utf-8").close()
        chosen_line = random.choice(lines_a)
    else:
        weighted_remaining = list(remaining_counter.elements())
        chosen_line = random.choice(weighted_remaining)

    os.makedirs(choice_history_dir, exist_ok=True)

    with open(selection_history, "a", encoding="utf-8") as fb:
        fb.write(chosen_line + "\n")

    logger.info(f"Randomly selected text from {options_source}: {chosen_line} (rand_val={rand_val:.4f} <= threshold={threshold})")

    return chosen_line