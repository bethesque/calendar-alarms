import pytest
from ecal.alarms.mpd import FadeOut, FadeUp


class TestFadeOutCalculateVolumeSteps:
    """Test the calculate_volume_steps static method in FadeOut."""

    def test_calculate_volume_steps_with_10_steps(self):
        """Test with 10 steps returns volumes from 45 to 0."""
        result = FadeOut.calculate_volume_steps(10, 50, 0)
        expected = [45, 40, 35, 30, 25, 20, 15, 10, 5, 0]
        assert result == expected

    def test_calculate_volume_steps_with_5_steps(self):
        """Test with 5 steps returns volumes from 40 to 0."""
        result = FadeOut.calculate_volume_steps(5, 50, 0)
        expected = [40, 30, 20, 10, 0]
        assert result == expected

    def test_calculate_volume_steps_with_1_step(self):
        """Test with 1 step returns [100, 0]."""
        result = FadeOut.calculate_volume_steps(1, 50, 20)
        expected = [20]
        assert result == expected

    def test_calculate_volume_steps_with_0_steps(self):
        """Test with 0 steps returns [100, 0]."""
        with pytest.raises(Exception, match=r"num_steps \(0\) must be more than 0"):
            FadeOut.calculate_volume_steps(0, 50, 0)

    def test_calculate_volume_steps_with_target_greater_than_current(self):
        result = FadeOut.calculate_volume_steps(5, 0, 50)
        expected = [50]
        assert result == expected


class TestFadeUpCalculateVolumeSteps:
    """Test the calculate_volume_steps static method in FadeUp."""

    def test_calculate_volume_steps_from_0_to_100_with_10_steps(self):
        """Test volume steps from 0 to 100 with 10 steps."""
        result = FadeUp.calculate_volume_steps(10, 0, 100)
        expected = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        assert result == expected

    def test_calculate_volume_steps_from_50_to_100_with_5_steps(self):
        """Test volume steps from 50 to 100 with 5 steps."""
        result = FadeUp.calculate_volume_steps(5, 50, 100)
        expected = [50, 60, 70, 80, 90, 100]
        assert result == expected

    def test_calculate_volume_steps_from_90_to_100_with_2_steps(self):
        """Test volume steps from 90 to 100 with 2 steps."""
        result = FadeUp.calculate_volume_steps(2, 90, 100)
        expected = [90, 95, 100]
        assert result == expected

    def test_calculate_volume_steps_same_current_and_target(self):
        """Test when current_volume equals target_volume."""
        result = FadeUp.calculate_volume_steps(5, 50, 50)
        expected = [50]
        assert result == expected

    def test_calculate_volume_steps_negative_step(self):
        """Test when target is less than current (should still work)."""
        result = FadeUp.calculate_volume_steps(5, 100, 50)
        # Since range goes from current to target, it will be empty, then append target
        expected = [50]
        assert result == expected

    def test_calculate_volume_steps_large_range(self):
        """Test with larger range."""
        result = FadeUp.calculate_volume_steps(4, 0, 100)
        expected = [0, 25, 50, 75, 100]
        assert result == expected
