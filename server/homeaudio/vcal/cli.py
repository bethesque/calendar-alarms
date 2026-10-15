import logging
import os
import time
from datetime import datetime, timedelta

from homeaudio.env import NOTIFICATIONS_CHECK_INTERVAL_MINUTES, LOG_LEVEL, GOOGLE_TRANSLATE_TLD_OPTIONS
from homeaudio.vcal import ALL_SENTENCES, snoozing_message
from homeaudio.vcal.cal.google_calendar import CalendarSource, Event, refresh_calendar_data as do_refresh_calendar_data
from homeaudio.audio.log_config import setup_logging_for_data_refresh, setup_logging
from homeaudio.vcal.event_notifications.text_to_voice import text_to_voice_file, TextToSpeechError, TextToSpeechRateLimitError
from homeaudio.vcal.core import EventNotificationSettings
from homeaudio.vcal.event_notifications.text import all_greeting_options
from homeaudio.audio.settings import GoogleCalendarSettings

"""
This script refreshes the calendar data and saves it to a local file.
"""

logger = logging.getLogger(__name__)

def refresh_calendar_data():
    do_refresh_calendar_data()

def insert_test_event():
    calendar_source = CalendarSource()
    calendar_days = calendar_source.load_data_from_file()
    # find the calendar day for the current date
    today = next(day for day in calendar_days if day.date == datetime.now().date())
    start_time = datetime.now().astimezone() + timedelta(minutes=NOTIFICATIONS_CHECK_INTERVAL_MINUTES + 1)
    event = Event(
        summary="A dynamically inserted test event",
        description="#announce",
        calendar_id="1",
        start_time=start_time,
        recurring=False,
        location=None,
        owner="Beth",
        owner_count=1,
    )
    today.timed_events.append(event)
    calendar_source.save_data_to_file()




def generate_sentence_audio_files():
    setup_logging(level=logging.DEBUG, log_file=None, stdout=True, http_debug=0)
    logging.getLogger("gtts.tts").setLevel(logging.WARNING)
    logging.getLogger("gtts.lang").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    sentences = list(ALL_SENTENCES)
    min_snooze = EventNotificationSettings().snooze_minutes - NOTIFICATIONS_CHECK_INTERVAL_MINUTES
    max_snooze = EventNotificationSettings().snooze_minutes
    sentences.extend([snoozing_message(i) for i in range(min_snooze, max_snooze + 1)])
    owners = [calendar.name for calendar in GoogleCalendarSettings().calendars if calendar.owner_count > 0]
    sentences.extend(greeting for greeting in all_greeting_options(owners) if greeting not in sentences)

    for tld in GOOGLE_TRANSLATE_TLD_OPTIONS:
        for sentence in sentences:
            try:
                print([sentence, tld])
                audio_file_path = text_to_voice_file(sentence, tld=tld)
            except TextToSpeechRateLimitError:
                logger.error("Rate limited by TTS API, stopping. Re-run later to generate the remaining files.")
                raise
            except TextToSpeechError as e:
                logger.error("Failed to generate audio for %r with tld %s: %s", sentence, tld, e)
                time.sleep(1)
                continue
            if time.time() - os.path.getmtime(audio_file_path) < 5:
                time.sleep(1)
