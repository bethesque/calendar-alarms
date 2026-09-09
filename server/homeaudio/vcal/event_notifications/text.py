import logging
import re
import random
from homeaudio.audio.random_text import ListOptionsSource, select_option_pseudorandomly
from homeaudio.vcal.cal.google_calendar import EventNotification
from pathlib import Path

logger = logging.getLogger(__name__)

class VerbIdentifier:
    def __init__(self, verb_file: str):
        with open(verb_file, encoding="utf-8") as f:
            self.verbs = set({line.strip() for line in f if line.strip()})

    def is_verb(self, word: str):
        return word.lower() in self.verbs

class NotificationTextBuilder:
    COMPLIMENTS_FOR_1 = ListOptionsSource("compliments_for_1", ["What a beautiful name.", "Everyone loves working with you.", "You are fabulous.", "What beautiful eyes you have.", "You're the best!", "You are one of the most talented people we know.", "Lots of people love you.", "You are thoughful, intelligent and beautiful."])
    COMPLIEMENTS_FOR_2 = ListOptionsSource("compliments_for_2", ["What a great looking pair you are.", "You're both awesome.", "It's a great day because you're here."])
    COMPLIEMENTS_FOR_MANY = ListOptionsSource("compliments_for_many", ["What a good looking bunch you are.", "You are all awesome."])

    CHANCE_OF_ANNOUNCEMENT_WITH_EXTRAS = 3/4

    def __init__(self, event_notifications: list[EventNotification], base_time):
        self.event_notifications = event_notifications
        self.base_time = base_time
        self.verb_identifier = VerbIdentifier(str(Path(__file__).resolve().parent.joinpath("verbs.txt")))

    def build(self) -> list[str]:
        if not self.event_notifications:
            return []

        parts = []

        if self.all_notifications_for_same_calendar() and self._add_extras():
            self.add_notification_text_with_extras(parts)
        else:
            for event in self.event_notifications:
                self._add_core_notification_text(event, parts)

        return parts

    def add_notification_text_with_extras(self, parts):

        first_notification = self.event_notifications[0]

        parts.append(self._greeting(first_notification))

        extra = self._select_type_of_extra(first_notification)
        logger.info(f"Adding extra {extra}")

        if extra == "compliment" and (comp := self._compliment(first_notification.event.owner_count)):
            parts.append(comp)

        for event in self.event_notifications:
            self._add_core_notification_text(event, parts)

        if extra == "encouragement":
            parts.append(self._encouragement())

    def all_notifications_for_same_calendar(self) -> bool:
        calendar_ids = {event_notification.event.calendar_id for event_notification in self.event_notifications}
        return len(calendar_ids) <= 1

    def _add_extras(self):
        return random.random() < self.CHANCE_OF_ANNOUNCEMENT_WITH_EXTRAS

    def _add_core_notification_text(self, event_notification: EventNotification, announcement: list[str]):
        if event_notification.notification_rule and event_notification.notification_rule.replace and event_notification.notification_rule.reminder:
            # Append the reminder only, no summary
            announcement.append(event_notification.notification_rule.reminder)
        else:
            # Append "it will be time..."
            announcement.append(self._it_will_be_time_for_summary(event_notification))

            if event_notification.notification_rule and event_notification.notification_rule.reminder:
                # Append the reminder
                announcement.append(event_notification.notification_rule.reminder)


    # Add a compliment, an encouragement, or nothing
    def _select_type_of_extra(self, event_notification):
        extras: list[str|None] = [None]
        # Only do encouragement for individuals and groups
        if event_notification.event.owner_count > 0:
            extras.append("compliment")
            extras.append("encouragement")
        # 1/3 of the time, do a compliment
        # 1/3 of the time, do an encouragement
        # 1/3 of the time, do neither
        extra = random.choice(extras)
        return extra

    def _it_will_be_time_for_summary(self, event_notification: EventNotification):
        summary = event_notification.event.summary
        if event_notification.offset > 0:
            return f"It will be time {self._to_or_for(summary)} {summary} in {event_notification.offset} minutes."
        else:
            return f"It's time {self._to_or_for(summary)} {summary}."

    def _greeting(self, event_notification: EventNotification):
        good_greeting = "Good morning" if self.base_time.hour < 12 else "Good afternoon" if self.base_time.hour < 17 else "Good evening"

        choices = [
            f"{good_greeting}.",
            "Hi there.",
            "Hey.",
            "Hey there.",
            "Hello.",
        ]

        if event_notification.event.owner_count > 0:
            choices.extend([
                f"{good_greeting} {event_notification.event.owner}.",
                f"Hi {event_notification.event.owner}. ",
                f"Hey {event_notification.event.owner}.",
                f"Hey there {event_notification.event.owner}.",
                f"Hello {event_notification.event.owner}.",
                f"Attention {event_notification.event.owner}.",
            ])

        return random.choice(choices)

    def _compliment(self, owner_count: int) -> str | None:
        if owner_count == 1:
            return select_option_pseudorandomly(None, 1, self.COMPLIMENTS_FOR_1)
        elif owner_count == 2:
            return select_option_pseudorandomly(None, 1, self.COMPLIEMENTS_FOR_2)
        else:
            return select_option_pseudorandomly(None, 1, self.COMPLIEMENTS_FOR_MANY)

    def _encouragement(self) -> str:
        return random.choice(["You can do it!", "Tiny potato believes in you!", "You're the best!", "You're capable of great things!", "You've got this!", "Be proud of yourself."])

    def _to_or_for(self, event_summary):
        first_word = re.sub(r"[^\w]", "", event_summary.split()[0]).lower()
        return "to" if self.verb_identifier.is_verb(first_word) else "for"
