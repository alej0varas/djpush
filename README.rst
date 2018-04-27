========
 Djpush
========

Manage programatic *Push Notifications* from Django admin.

Features
========

 - Define notifications via the admin
 - Categorize notifications
 - Schedule notifications by category
 - Choose your provider(APNS/apns2, GCM/gcm, OneSignal/yaosac). Actually you must install one.
 - Same notification in time range are canceled
 - (optional) Multiple language support via django-modelstranslation

Important Dependencies
======================

 - celery
 - django-timezone-field
 - pytz

Usage
=====

In your `settings.py` define:

DJPUSH_NOTIFICATIONS_CHOICES
  A list of `slugs <https://docs.djangoproject.com/en/1.11/glossary/#term-slug>`_ representing the notifications you want to send.
DJPUSH_DEFAULT_PROVIDER
  The provider you want to use to send notifications(values can be found in `pypn <https://github.com/alej0varas/pypn>`_).
optional settings
DJPUSH_NOTIFICATION_EXPIRES
  The number of seconds after task will be considered expired

.. code-block:: python

   # Get a notification, you define them in the admin
   notification = models.Notification.objects.get(slug='a-slug', enabled=True)

   # Create a notification instance
   notification_instance = models.NotificationInstance.objects.create(notification=notification, tokens=tokens, data=data)

   # Send the notification
   notification_instance.send()

Development
===========

Update migrations
-----------------

::

   DJANGO_SETTINGS_MODULE=migration_settings django-admin makemigrations

Run tests
---------

::

   ./runtests.py

Build/Publish
-------------

::

   rm -rf dist
   python setup.py sdist bdist_wheel
   twine upload dist/*

Translations
------------

To enable translations you have to install `django-modeltranslation`
and add `MIGRATION_MODULES = {'djpush': 'djangoproject.migrations'}`
to your settings.

Notifications will be sent including the available tranlations.
