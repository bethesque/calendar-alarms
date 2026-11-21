import pytest

from homeaudio.audio.music_assistant import PlayerFadeOut


def test_calculate_volume_steps_fades_from_full_volume_to_zero():
    volumes = PlayerFadeOut.calculate_volume_steps(10, 1.0, 0.0)

    assert volumes == pytest.approx([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0])


def test_calculate_volume_steps_fades_to_non_zero_target():
    volumes = PlayerFadeOut.calculate_volume_steps(4, 0.8, 0.4)

    assert volumes == pytest.approx([0.7, 0.6, 0.5, 0.4])


def test_calculate_volume_steps_ends_at_target_volume():
    volumes = PlayerFadeOut.calculate_volume_steps(7, 0.63, 0.12)

    assert volumes[-1] == 0.12
    assert len(volumes) == 7


def test_calculate_volume_steps_with_single_step_returns_current_and_target():
    assert PlayerFadeOut.calculate_volume_steps(1, 0.5, 0.0) == [0.0]


@pytest.mark.parametrize("num_steps", [0, -1])
def test_calculate_volume_steps_with_non_positive_num_steps_returns_only_target(num_steps):
    assert PlayerFadeOut.calculate_volume_steps(num_steps, 0.5, 0.2) == [0.2]


def test_calculate_volume_steps_with_unknown_current_volume_returns_only_target():
    assert PlayerFadeOut.calculate_volume_steps(10, None, 0.2) == [0.2]


def test_calculate_volume_steps_clamps_target_volume_above_one():
    volumes = PlayerFadeOut.calculate_volume_steps(2, 0.5, 1.5)

    assert volumes == pytest.approx([0.75, 1.0])


def test_calculate_volume_steps_clamps_target_volume_above_one_when_current_volume_unknown():
    assert PlayerFadeOut.calculate_volume_steps(10, None, 2.0) == [1.0]


def test_calculate_volume_steps_ramps_up_when_current_volume_below_target():
    volumes = PlayerFadeOut.calculate_volume_steps(4, 0.2, 0.6)

    assert volumes == pytest.approx([0.3, 0.4, 0.5, 0.6])


def test_calculate_volume_steps_does_not_append_extra_step_when_current_volume_equals_target():
    assert PlayerFadeOut.calculate_volume_steps(3, 0.5, 0.5) == [0.5, 0.5, 0.5]

def test_calculate_volume_steps_with_1_step_2():
    """Test with 1 step returns [100, 0]."""
    result = PlayerFadeOut.calculate_volume_steps(1, 0.4, 0.15)
    expected = [0.15]
    assert result == expected