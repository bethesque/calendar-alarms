from homeaudio.vcal.playback import NotificationFile, NotificationFiles


def test_targets_returns_none_when_there_are_no_files():
    assert NotificationFiles().targets() is None


def test_targets_returns_none_when_all_files_have_no_targets():
    notification_files = NotificationFiles(
        event_alarms_file=NotificationFile(path="alarm.wav", targets=None),
        event_announcements_file=NotificationFile(path="announcement.wav", targets=None),
    )

    assert notification_files.targets() is None


def test_targets_returns_the_shared_target_when_all_files_agree():
    notification_files = NotificationFiles(
        event_alarms_file=NotificationFile(path="alarm.wav", targets=frozenset({"kitchen"})),
        event_announcements_file=NotificationFile(path="announcement.wav", targets=frozenset({"kitchen"})),
        scheduled_announcements_files=[NotificationFile(path="scheduled.wav", targets=frozenset({"kitchen"}))],
    )

    assert notification_files.targets() == ["kitchen"]


def test_targets_returns_none_when_files_have_different_targets():
    notification_files = NotificationFiles(
        event_alarms_file=NotificationFile(path="alarm.wav", targets=frozenset({"kitchen"})),
        event_announcements_file=NotificationFile(path="announcement.wav", targets=frozenset({"bedroom"})),
    )

    assert notification_files.targets() is None


def test_targets_returns_none_when_one_file_has_no_targets_and_another_does():
    notification_files = NotificationFiles(
        event_alarms_file=NotificationFile(path="alarm.wav", targets=frozenset({"kitchen"})),
        event_announcements_file=NotificationFile(path="announcement.wav", targets=None),
    )

    assert notification_files.targets() is None
