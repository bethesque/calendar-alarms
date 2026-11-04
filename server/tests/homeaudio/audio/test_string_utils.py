from homeaudio.audio.string_utils import add_missing_full_stops


def test_add_missing_full_stops_adds_a_full_stop_to_sentences_without_ending_punctuation_or_a_colon():
    assert add_missing_full_stops(["Events are:", "Meeting", "Done.", "Ready?", "Hooray!"]) == ["Events are:", "Meeting.", "Done.", "Ready?", "Hooray!"]
