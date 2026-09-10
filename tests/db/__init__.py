"""
DB test suite.

Tests that talk to RiveAr's Postgres database directly, bypassing the
API, to verify rules the database enforces itself (CHECK constraints,
generated columns) - independent of whatever the application layer above
it does or doesn't validate.
"""
