from dataclasses import dataclass
from datetime import datetime
import logging
import re
import random
from homeaudio.audio.random_text import ListOptionsSource, select_option_pseudorandomly
from homeaudio.vcal import GREETINGS, COMPLIMENTS_FOR_1, COMPLIMENTS_FOR_2, COMPLIMENTS_FOR_MANY, ENCOURAGEMENTS, GOOD_GREETINGS, GOOD_MORNING, GOOD_AFTERNOON, GOOD_EVENING
from homeaudio.vcal.event_notifications.events import EventNotification
from pathlib import Path

logger = logging.getLogger(__name__)

def greeting_options(good_greeting: str, owner: str | None = None) -> list[str]:
    options = [good_greeting, *GREETINGS]
    if owner:
        options.extend([
            f"{good_greeting} {owner}",
            f"Hi {owner}",
            f"Hey {owner}",
            f"Hey there {owner}",
            f"Hello {owner}",
            f"Attention {owner}",
        ])
    return options

def all_greeting_options(owners: list[str]) -> list[str]:
    """
    Used for pre-generating audio files
    """
    return list(dict.fromkeys(
        option
        for good_greeting in GOOD_GREETINGS
        for owner in [None, *owners]
        for option in greeting_options(good_greeting, owner)
    ))

def _to_or_for(event_summary, verb_identifier: VerbIdentifier):
    first_word = re.sub(r"[^\w]", "", event_summary.split()[0]).lower()
    return "to" if verb_identifier.is_verb(first_word) else "for"

def what_it_is_time_for_or_to(summary: str, household_names: list[str], verb_identifier: VerbIdentifier) -> str:
    for name in household_names:
        prefix = f"{name} "
        if summary.lower().startswith(prefix.lower()):
            rest = summary[len(prefix):].lstrip()
            if rest and _to_or_for(rest, verb_identifier) == "to":
                return f"for {summary[:len(name)]} to {rest}"
    return f"{_to_or_for(summary, verb_identifier)} {summary}"


class VerbIdentifier:
    def __init__(self, verb_file: str | None = None):
        verb_file = verb_file or str(Path(__file__).resolve().parent.joinpath("verbs.txt"))
        with open(verb_file, encoding="utf-8") as f:
            self.verbs = set({line.strip() for line in f if line.strip()})

    def is_verb(self, word: str):
        return word.lower() in self.verbs

@dataclass
class TemplateOption:
    template: str
    min: int | None = None
    max: int | None = None

    def matches(self, minutes):
        return (self.min is None or self.min <= minutes) and (self.max is None or minutes < self.max)

def get_template_options(event_notification: EventNotification, household_names: list[str], verb_identifier: VerbIdentifier):
    summary = event_notification.event.summary
    start_time = event_notification.event.start_time
    thing_it_is_time_for = what_it_is_time_for_or_to(summary, household_names, verb_identifier)

    options = []

    start_text = f"{start_time.hour % 12 or 12}:{start_time.minute:02d}{'am' if start_time.hour < 12 else 'pm'}"

    options.append(TemplateOption(min=None, max=-60, template=f"It was time {thing_it_is_time_for} at {start_text}."))
    options.append(TemplateOption(min=-60, max=-1, template=f"It was time {thing_it_is_time_for} {{mins}} minutes ago."))
    options.append(TemplateOption(min=-1, max=0, template=f"It was time {thing_it_is_time_for} {{mins}} minute ago."))
    options.append(TemplateOption(min=0, max=1, template=f"It's time {thing_it_is_time_for}."))
    options.append(TemplateOption(min=1, max=2, template=f"It will be time {thing_it_is_time_for} in {{mins}} minute."))
    options.append(TemplateOption(min=2, max=None, template=f"It will be time {thing_it_is_time_for} in {{mins}} minutes."))
    return options


class NotificationTextBuilder:
    COMPLIMENTS_FOR_1 = ListOptionsSource("compliments_for_1", COMPLIMENTS_FOR_1)
    COMPLIEMENTS_FOR_2 = ListOptionsSource("compliments_for_2", COMPLIMENTS_FOR_2)
    COMPLIEMENTS_FOR_MANY = ListOptionsSource("compliments_for_many", COMPLIMENTS_FOR_MANY)

    CHANCE_OF_ANNOUNCEMENT_WITH_EXTRAS = 3/4

    def __init__(self, event_notifications: list[EventNotification], base_time, household_names: list[str] | None = None):
        self.event_notifications = event_notifications
        self.base_time = base_time
        self.household_names = household_names or []
        self.verb_identifier = VerbIdentifier()

    def build(self) -> list[str]:
        if not self.event_notifications:
            return []

        parts = []

        if self.all_notifications_for_same_calendar() and self._add_extras():
            self.add_notification_text_with_extras(parts)
        else:
            for event in self.event_notifications:
                self._add_core_notification_text(event, parts)

        return list(dict.fromkeys(parts))

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
        if event_notification.event.owner_count > 0 and not self._any_summary_starts_with_persons_name():
            extras.append("compliment")
            extras.append("encouragement")
        # 1/3 of the time, do a compliment
        # 1/3 of the time, do an encouragement
        # 1/3 of the time, do neither
        extra = random.choice(extras)
        return extra

    def _it_will_be_time_for_summary(self, event_notification: EventNotification):
        minutes_until_start = int((event_notification.event.start_time - self.base_time).total_seconds() / 60)
        options = get_template_options(event_notification, self.household_names, self.verb_identifier)
        option = next(option for option in options if option.matches(minutes_until_start))
        return option.template.replace("{mins}", str(abs(minutes_until_start)))

    def _greeting(self, event_notification: EventNotification):
        good_greeting = GOOD_MORNING if self.base_time.hour < 12 else GOOD_AFTERNOON if self.base_time.hour < 17 else GOOD_EVENING
        owner = event_notification.event.owner if event_notification.event.owner_count > 0 and not self._any_summary_starts_with_persons_name() else None
        return random.choice(greeting_options(good_greeting, owner))

    def _compliment(self, owner_count: int) -> str | None:
        if owner_count == 1:
            return select_option_pseudorandomly(None, 1, self.COMPLIMENTS_FOR_1)
        elif owner_count == 2:
            return select_option_pseudorandomly(None, 1, self.COMPLIEMENTS_FOR_2)
        else:
            return select_option_pseudorandomly(None, 1, self.COMPLIEMENTS_FOR_MANY)

    def _encouragement(self) -> str:
        return random.choice(ENCOURAGEMENTS)

    def _any_summary_starts_with_persons_name(self) -> bool:
        return any(
            event_notification.event.summary.lower().startswith(f"{name} ".lower())
            for event_notification in self.event_notifications
            for name in self.household_names
        )


