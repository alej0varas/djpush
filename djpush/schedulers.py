import datetime


# Schedulers return the `datetime.datetime` a task should be scheduled.


class SchedulerMinutesLater:
    """Schedule the tasks `minutes` later"""

    def __init__(self, minutes=0):
        self.minutes = minutes

    def __call__(self, now):
        return now + datetime.timedelta(minutes=self.minutes)


class SchedulerInTimeRange:
    """Schedule the tasks in a time range. If not possible today schedule
    for tomorrow. For example: Given `lower_limit` is 8,
    `higher_limit` is 22. If `now` is 14 the result is today at 14. If
    `now` is 7 the result is today at `lower_limit`. If `now` is 23
    the result is tomorrow at `lower_limit`.

    """
    def __init__(self, start_hour, end_hour, discard):
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.discard = discard

    def __call__(self, now):
        # It's too early
        if now.hour < self.start_hour:
            days = 0
        # It's too late
        elif now.hour >= self.end_hour:
            days = 1
        # No need to schedule
        else:
            return now

        # We are not in the time range and we don't want to schedule
        if self.discard:
            return None

        delta = datetime.timedelta(days=days)
        tomorrow = now + delta
        tomorrow_at = tomorrow.replace(hour=self.start_hour, minute=0, second=0)
        return tomorrow_at
