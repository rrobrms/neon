from fixtures.neon_fixtures import NeonEnvBuilder, WalGenerate
from fixtures.log_helper import log
import pytest

# Ensure that complicated WALs are correctly handled by the whole stack.


@pytest.mark.parametrize('wal_type',
                         [
                             'simple',
                             'last_wal_record_xlog_switch',
                             'last_wal_record_xlog_switch_ends_on_page_boundary',
                             'last_wal_record_crossing_segment',
                             'wal_record_crossing_segment_followed_by_small_one',
                         ])
def test_wal_generate(neon_env_builder: NeonEnvBuilder, wal_type: str):
    neon_env_builder.num_safekeepers = 1
    env = neon_env_builder.init_start()
    env.neon_cli.create_branch('test_wal_generate')

    pg = env.postgres.create('test_wal_generate')
    gen = WalGenerate(env)
    pg.config(gen.postgres_config())
    pg.start()
    res = pg.safe_psql_many(queries=[
        'CREATE TABLE keys(key int primary key)',
        'INSERT INTO keys SELECT generate_series(1, 100)',
        'SELECT SUM(key) FROM keys'
    ])
    assert res[-1][0] == (5050, )

    gen.in_existing(wal_type, pg.connstr())

    log.info("Restarting all safekeepers and pageservers")
    env.pageserver.stop()
    env.safekeepers[0].stop()
    env.safekeepers[0].start()
    env.pageserver.start()

    log.info("Trying more queries")
    res = pg.safe_psql_many(queries=[
        'SELECT SUM(key) FROM keys',
        'INSERT INTO keys SELECT generate_series(101, 200)',
        'SELECT SUM(key) FROM keys',
    ])
    assert res[0][0] == (5050, )
    assert res[-1][0] == (20100, )

    log.info("Restarting all safekeepers and pageservers (again)")
    env.pageserver.stop()
    env.safekeepers[0].stop()
    env.safekeepers[0].start()
    env.pageserver.start()

    log.info("Trying more queries (again)")
    res = pg.safe_psql_many(queries=[
        'SELECT SUM(key) FROM keys',
        'INSERT INTO keys SELECT generate_series(201, 300)',
        'SELECT SUM(key) FROM keys',
    ])
    assert res[0][0] == (20100, )
    assert res[-1][0] == (45150, )
