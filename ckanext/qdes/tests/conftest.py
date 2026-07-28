# encoding: utf-8
import pytest
import redis


@pytest.fixture(autouse=True, scope='session')
def _copyable_redis_client():
    """Allow CKAN's `ckan_config` fixture to copy the application config.

    CKAN stores a live Redis client in `SESSION_REDIS` (see
    CKANRedisSessionInterface), and the `ckan_config` fixture that
    `with_plugins` depends on takes a deepcopy of the config. A Redis client
    holds a thread lock and cannot be deepcopied, so any test using those
    fixtures fails with "cannot pickle '_thread.lock' object".

    The connection pool is a shared resource that should not be duplicated for
    a copy of the config anyway, so copying yields the same client.
    """
    if not hasattr(redis.Redis, '__deepcopy__'):
        redis.Redis.__deepcopy__ = lambda self, memo: self
    yield


@pytest.fixture
def clean_db(reset_db, migrate_db_for, with_plugins):
    """Reset the database, refusing to run against a non-test database.

    CKAN's own `clean_db` drops and recreates every table in whatever database
    `sqlalchemy.url` names. Running the suite with
    `--ckan-ini=/app/config/ckan.ini` therefore destroys all local development
    data. Overriding the fixture here fails loudly instead, and only for tests
    that actually ask for a database.

    Depends on `with_plugins` so plugins are loaded before `migrate_db_for`,
    which resolves migrations via the plugin registry.
    """
    # Imported lazily: importing ckan.common at module scope triggers CKAN's
    # environment bootstrap, which fails when the unit suite runs with
    # `-p no:ckan`. Only database-backed tests reach this point.
    from ckan.common import config

    url = config.get('sqlalchemy.url') or ''
    database = url.rsplit('/', 1)[-1].split('?')[0]
    if 'test' not in database:
        pytest.fail(
            'Refusing to reset database "{0}": it is not a test database and '
            'resetting it would destroy local development data. Run with a '
            'ckan ini whose sqlalchemy.url names a test database.'.format(
                database))
    reset_db()
    # `reset_db` only creates CKAN core's tables. The activity plugin ships its
    # own migrations (permission_labels), without which any action that writes
    # an activity record fails.
    migrate_db_for('activity')
