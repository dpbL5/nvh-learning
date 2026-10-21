#!/bin/bash
set -e
# Install dependencies
python3.12 -m pip install -r requirements.txt
# Apply database migrations
python3.12 manage.py migrate --noinput
# Create the DatabaseCache table if it does not exist
python3.12 manage.py createcachetable
# Run collectstatic
python3.12 manage.py collectstatic --noinput
