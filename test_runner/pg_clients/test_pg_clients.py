import os
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import pytest
from fixtures.neon_fixtures import RemotePostgres


@pytest.mark.remote_cluster
@pytest.mark.parametrize(
    "client",
    [
        "csharp/npgsql",
        "java/jdbc",
        "python/asyncpg",
        pytest.param("python/pg8000", marks=pytest.mark.xfail(reason="Doesn't support SNI")),
        pytest.param("swift/PostgresClientKit",
                     marks=pytest.mark.xfail(reason="Doesn't support SNI")),
        "typescript/postgresql-client",
    ],
)
def test_pg_clients(remote_pg: RemotePostgres, client: str):
    conn_options = remote_pg.conn_options()

    env_file = None
    with NamedTemporaryFile(mode='w', delete=False) as f:
        env_file = f.name
        f.write(f"""
            NEON_HOST={conn_options["host"]}
            NEON_DATABASE={conn_options["dbname"]}
            NEON_USER={conn_options["user"]}
            NEON_PASSWORD={conn_options["password"]}
        """)

    image_tag = client.lower()
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        raise RuntimeError("docker is required for running this test")

    build_cmd = [
        docker_bin, "build", "--quiet", "--tag", image_tag, f"{Path(__file__).parent / client}"
    ]
    run_cmd = [docker_bin, "run", "--rm", "--env-file", env_file, image_tag]

    subprocess.run(build_cmd, check=True)
    result = subprocess.run(run_cmd, check=True, capture_output=True, text=True)

    assert result.stdout.strip() == "1"
