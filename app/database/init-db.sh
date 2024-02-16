#!/bin/bash

# TODO: This should be cleaned up (moved to db container?) eventually
locations_file='/tmp/locations.csv'
feeds_file='/tmp/feeds.csv'

# Function to check if db is responding
db_conn () {
    psql -d $PGDATABASE
}

# Function to check if db has already been initialized (feeds table is present)
db_exists () {
    psql -d $PGDATABASE -XtAc "SELECT 1 FROM pg_tables WHERE tablename = 'feeds';"
}

# small sleep to let db spin up first (may need to adjust this in future)
sleep 10

# Run check - retry 10 times
for i in {1..10}
do
  echo "Reaching out to database"
  db_conn
  # If db_conn function returns non-zero code, database was not ready / didn't respond nicely
  if [ $? -ne 0 ]; then
    echo "Database not available yet (retry count: $i), sleeping..."
    sleep 20
    continue
  else
    echo "database has agreed to speak with me - very nice!"
    # database responds, does table exist?
    if [ "$(db_exists)" != '1' ]; then
      # after this point, script should crash from any non-zero returns
      set -e
      echo "tables aren't there yet - initializing database..."
      # init schema
      psql -d $PGDATABASE -c "CREATE SCHEMA IF NOT EXISTS $PGSCHEMA AUTHORIZATION $PGUSER"
      # replace {SCHEMA} tag in schema file
      sed -i "s/{SCHEMA}/$PGSCHEMA/g" "/schema.sql"
      # write schema file
      psql -d $PGDATABASE -f "/schema.sql"
      # populate location data
      psql -d $PGDATABASE -c "COPY $PGSCHEMA.locations (id, name, latitude, longitude) FROM '$locations_file' WITH (FORMAT csv, DELIMITER ',', HEADER);"
      # populate feed data
      psql -d $PGDATABASE -c "COPY $PGSCHEMA.feeds (name, url, type, location, status) FROM '$feeds_file' WITH (FORMAT csv, DELIMITER ',', HEADER);"
      echo "database successfully initialized (unless you see a bunch of errors above this in the logs...)"
      exit 0
    else
      echo "database already set up - skipping."
      exit 0
    fi
  fi
  echo "database did not respond or database $PGDATABASE does not exist"
  exit 1
done
