#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate

python manage.py ensure_superuser
python manage.py seed_allergens # Creates database entries for basic allergens
python manage.py seed_recipes # Creates database entries for recipes