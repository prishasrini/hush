# Hush database setup

The app uses PostgreSQL when DATABASE_URL is set; otherwise it uses the local
hush.db next to database.py. SQLITE_PATH can override the local file for tests.
A failed PostgreSQL connection stops startup instead of falling back to SQLite.

## Supabase and Render

1. Keep the Supabase Data API disabled. Use Connect > Session pooler > URI.
2. In Render's private environment settings, add DATABASE_URL with that URI.
   Replace the password placeholder privately. URL-encode special characters
   in the password component; do not encode the entire URI or use an online
   password encoder. Never commit the URL or paste it into chat.
3. Deploy the updated code with `pip install -r requirements.txt` as the build
   step. The existing application start command can stay the same.
4. Startup creates missing tables without removing existing rows. Confirm a
   successful startup, then verify registration, login and a mood check-in.
5. Restart the service and confirm the new account and mood still exist.

PostgreSQL connections require TLS and use a 10-second connection timeout.
This uses sslmode=require (transport encryption, not full certificate identity
verification); stronger certificate verification can be configured in a later
hardening pass. The connection is intended for Supabase's session pooler.

## Existing data

Switching databases does NOT migrate old accounts, moods or messages. The live
Render SQLite file and the laptop's SQLite file are separate. Before switching
or redeploying, preserve the live SQLite database if its contents matter: a
Render redeploy may discard an ephemeral SQLite file. Plan and verify a separate
migration; this change does not read, export, upload, or delete existing data.

## Tests and remaining work

Run `python -m unittest test_database` after installing requirements. Tests use
a temporary SQLite database and mocked PostgreSQL connections; they do not
validate the live Supabase credentials or network connection.

This change adds database compatibility only. It does not implement the planned
privacy changes. Existing chat logging, session-secret configuration, deletion
controls and privacy wording still need their own updates before wider use.
Passwords continue to be hashed by the existing registration code. Other stored
content is not end-to-end encrypted and can be read by a database administrator.
