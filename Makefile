test:
	DJANGO_SETTINGS_MODULE=tests.settings py.test tests/

demo:
	python manage.py runserver --settings=tests.demo_settings
