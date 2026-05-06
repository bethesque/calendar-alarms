import random
import os
from collections import Counter
import logging
from ecal.env import CACHE_DIRECTORY, RESOURCES_DIRECTORY

logger = logging.getLogger(__name__)

CHOICE_HISTORY_DIR = CACHE_DIRECTORY + "/random_text_selection_history"

"""
threshold is the probability of returning the randomly selected text instead of the default text.
For example, if threshold is 0.3, then there is a 30% chance of returning the randomly selected text and a 70% chance of returning the default text.
"""
def select_text(default_text: str | None,
                         threshold: float,
                         text_choices: str,
                         resources_directory=RESOURCES_DIRECTORY,
                         choice_history_dir = CHOICE_HISTORY_DIR) -> str | None:
    """
    - Generate a random float in [0, 1)
    - If rand_val > threshold:
        - Pick a line from text_choices (multiset-aware, excluding selection_history)
        - Append it to selection_history
        - Return the chosen line
    - Else:
        - Return default_text
    """

    text_choices_full_path = os.path.join(resources_directory, text_choices)

    selection_history = os.path.join(choice_history_dir, os.path.splitext(text_choices)[0] + "_history" + os.path.splitext(text_choices)[1])

    rand_val = random.random()

    if rand_val > threshold:
        logger.debug(f"Random value {rand_val:.4f} is greater than threshold {threshold}, returning default text: {default_text}")
        return default_text

    # if text_choices file doesn't exist, return default_text
    if not os.path.exists(text_choices_full_path):
        logger.warning(f"{text_choices_full_path} file not found. Cannot select random text. Returning default.")
        return default_text

    # Read text_choices
    with open(text_choices_full_path, "r", encoding="utf-8") as fa:
        lines_a = [line.rstrip("\n") for line in fa]

    if not lines_a:
        logger.debug(f"{text_choices_full_path} is empty. Returning default text.")
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

    logger.debug(f"Randomly selected text: {chosen_line} (rand_val={rand_val:.4f} <= threshold={threshold})")

    return chosen_line