from datetime import datetime
from unittest import mock

from django.test import TestCase
from pytz import timezone

from djpush import schedulers


class FakeDate(datetime):
    """A fake replacement for `datetime.datetime` that can be mocked for
    testing.

    """
    def __new__(cls, *args, **kwargs):
        return datetime.__new__(datetime, *args, **kwargs)


fake_now_args = None
tz = timezone('Europe/Paris')
scheduler_args = (8, 22, False)


def fake_now(self, tz=None):
    from datetime import datetime, timedelta, timezone
    if tz is not None:
        offset = timedelta(hours=2)
        tz = timezone(offset)
    return datetime(*fake_now_args, tzinfo=tz)


FakeDate.now = classmethod(fake_now)


@mock.patch('djpush.schedulers.datetime.datetime', FakeDate)
class SchedulerMinutesLaterTestCase(TestCase):
    def test_success(self):
        global fake_now_args
        fake_now_args = (2016, 9, 25, 22, 0, 0)

        result = schedulers.SchedulerMinutesLater()(datetime(*fake_now_args))
        self.assertEqual(result, datetime(*fake_now_args))

    def test_success_in_five_minutes(self):
        global fake_now_args
        fake_now_args = (2016, 9, 25, 22, 0, 0)

        result = schedulers.SchedulerMinutesLater(5)(datetime(*fake_now_args))
        self.assertEqual(
            result,
            datetime(*fake_now_args).replace(minute=fake_now_args[4] + 5))


@mock.patch('djpush.schedulers.datetime.datetime', FakeDate)
class SchedulerInTimeRangeTestCase(TestCase):
    """Test the day of the week functions."""
    def test_today_is_to_late(self):
        global fake_now_args
        fake_now_args = (2016, 9, 25, 22, 0, 0)

        result = schedulers.SchedulerInTimeRange(*scheduler_args)(datetime(*fake_now_args))

        self.assertEqual(result.day, fake_now_args[2] + 1)
        self.assertEqual(result.hour, scheduler_args[0])

    def test_today_but_later(self):
        global fake_now_args
        fake_now_args = (2016, 9, 25, 4, 0, 0)

        result = schedulers.SchedulerInTimeRange(*scheduler_args)(datetime(*fake_now_args))

        self.assertEqual(result.day, fake_now_args[2])
        self.assertEqual(result.hour, scheduler_args[0])

    def test_today_now(self):
        global fake_now_args
        fake_now_args = (2016, 9, 25, 14, 0, 0)

        result = schedulers.SchedulerInTimeRange(*scheduler_args)(datetime(*fake_now_args))

        self.assertEqual(result, datetime(*fake_now_args))

    def test_outside_working_discard(self):
        global fake_now_args
        fake_now_args = (2016, 9, 25, 3, 0, 0)
        scheduler_args_local = scheduler_args[:2] + (True, )
        result = schedulers.SchedulerInTimeRange(*scheduler_args_local)(datetime(*fake_now_args))

        self.assertEqual(result, None)
