# Calendar notifications

The Calendar Alarms app (aka Annabell) reads your Google Calendar and plays spoken alarms and announcements through the house speakers before your events.

There are two ways to get a notification for an event:

1. Add the text `#alarm` or `#announce` to the event's description in Google Calendar.
2. Set up a **notification rule** in the settings that matches events automatically based on their summary, description, location or calendar.

Notifications only play during the hours set in the notification schedule (weekdays, weekends and holidays can have different hours).

If you have an event that you do not wish to be read by the Calendar Alarms app, set its visibility to `Private` in the Google calendar event editing page.

## Tags

A Calendar Alarms tag is a word starting with a `#` in the event description that tells the app what sort of notification to play, and when to do it. If a tag has a number at the end (eg. `#announce5`), the notification will play that many minutes before the start of the event.

| Tag | What it does |
| --- | --- |
| `#alarm` / `#alarm<n>` | Plays an **alarm**: music that starts gently and gets louder, with the event summary read out repeatedly. |
| `#announce` / `#announce<n>` | Plays a short spoken **announcement** of the event. |
| `#depart<n>` | Sets your **departure time** to `<n>` minutes before the event. You get an announcement when it's time to leave, plus a heads-up a few minutes before that. |


You can use more than one tag on an event. For example, this description:

```
#alarm30 #announce5
```

plays an alarm 30 minutes before the event and an announcement 5 minutes before it.

All other text in the event description is ignored, and won't interfere with the notifications.

## Notification rules

Rules save you from needing to add tags to the same kind of event over and over, for example "announce 30 minutes before every gym event".

Each rule has:

- **What to match**: text to look for in the event's title, description or location, and/or a particular calendar. Matching ignores upper/lower case, and the text only needs to appear somewhere in the field. Every condition you fill in must match.
- **When**: how many minutes before the event starts.
- **Type**: alarm or announcement.
- **Reminder** (optional): extra words to say, such as "Remember to pack your earplugs." Turn on **replace** to say only the reminder, instead of reading out the event and then the reminder.

## Departure notifications

When departure notifications are enabled, any event that has a **location** gets a departure time calculated for it using Google Maps. The calculation allows time for getting from the house to the car, for parking, and a safety margin in case the estimate is optimistic, all of which are set by the user. The estimate is updated regularly as the event gets closer.

For each event with a location you get two announcements:

- A **heads-up** a few minutes before you need to leave
- A **time to leave** announcement - this is the time you need to *walk out your door*, taking into account the time it takes to get from your house to the car.

If you'd rather choose the departure time yourself, use `#depart<n>` eg. `#depart20`. To disable departure announcements for an event with a location, use `#nodepart`.

### Departure rules

Departure rules work like notification rules, with one difference: the minutes count back from the **departure time**, not from the start of the event. Use them for reminders about getting ready to go, for example "75 minutes before leaving for the gym: eat something now".
