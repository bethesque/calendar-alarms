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

There are 3 ways to get departure notifications.

1. Add a `#depart` tag with a number (eg. `#depart20`) in the event *description*.
2. Enter an address into the *location* of an event and the Calendar App will calculate the departure time automatically.
3. Create a Departure Rule based on the *summary* (eg. for all "Gym" events, set departure time to 10 minutes before the event start)

For each event with a departure notification you get two announcements:

- A **heads-up** a few minutes before you need to leave (you can configure how far ahead this happens in the settings)
- A **time to leave** announcement - this is the time you need to *walk out your door*.

To disable departure announcements for an event with a location, use `#nodepart` in the description. If there are multiple depature time sources (eg. a location and a tag ) then the first one in the list above will be used (tag with number trumps other sources, then location, then depature rule)

### Departure notifications based on calculated travel time

When location based departure notifications are enabled in the settings, any event that has a **location** gets a departure time calculated for it using Google Maps. The calculation allows time for getting from the house to the car, for parking, and a safety margin in case the estimate is optimistic, all of which are set by the user. The estimate is updated regularly as the event gets closer.

### Departure time rules

If you have regular events (eg. gym, scouts) that you want to set a specific departure time for, you can make a departure rule that allows you to specify "when the summary matches `<key word>` then the departure time will be `<x>` minutes before the event start". For example, "when the summary matches `gym` then set the departure time to `20` minutes before the event start time".

### Extra departure notifications

By default, the app will give you a "heads-up notification" and a "depart now" notification. If you would like to add extra notifications (eg. "remind me to have a snack to eat 60 minutes before I need to leave for gym") then you can create a notification rule where the notificating timing is based on the departure time, rather than the event start time.
