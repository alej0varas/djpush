#!/usr/bin/env python
import sys

import django
from django.conf import settings
import pypn


if not settings.configured:
    settings.configure(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=(
            'djpush',
        ),
        SITE_ID=1,
        SECRET_KEY='this-is-just-for-tests-so-not-that-secret',
        DEBUG=True,
        TEMPLATES = [
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [],
                'APP_DIRS': True,
            },
        ],
        DJPUSH_DEFAULT_PROVIDER=pypn.DUMMY,
    )


from django.test.utils import get_runner


def runtests():
    if hasattr(django, 'setup'):
        django.setup()
    apps = sys.argv[1:] or ['djpush', ]
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=1, interactive=True, failfast=False)
    failures = test_runner.run_tests(apps)
    sys.exit(failures)


if __name__ == '__main__':
    runtests()
