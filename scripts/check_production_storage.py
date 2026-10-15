"""Run production integration checks in an owned disposable TLS PostgreSQL.

Requires Docker, OpenSSL and the optional hashed production/auth dependencies.
Uses a digest-pinned official PostgreSQL image, ephemeral passwords and a test
CA. Creates and removes only its own container/network. No remote or paid
resources are provisioned; no DSN, password or private key is printed.
"""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
import psycopg
from psycopg import sql


def main():
    root = Path(__file__).resolve().parents[1]
    cli = ['env','-u','DOCKER_HOST','-u','DOCKER_CONTEXT','-u','DOCKER_TLS','-u','DOCKER_TLS_VERIFY','-u','DOCKER_CERT_PATH','docker','--host=unix:///var/run/docker.sock']
    container = 'vf-prod-check-' + secrets.token_hex(5)
    network = container+'-net'
    admin_password, app_password = secrets.token_urlsafe(30), secrets.token_urlsafe(30)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    def url(database, username, password, *, ca=None, internal=False):
        host, target_port = ('postgres.test.local',5432) if internal else ('127.0.0.1',port)
        transport = 'sslmode=disable' if ca is None else 'sslmode=verify-full&sslrootcert='+quote(str(ca),safe='')
        return f'postgresql://{username}:{quote(password)}@{host}:{target_port}/{database}?{transport}'
    environment = os.environ.copy()
    environment['POSTGRES_PASSWORD'] = admin_password
    try:
        subprocess.run(cli+['network','create',network],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(cli + ['run','--detach','--name',container,'--network',network,'--network-alias','postgres.test.local','--tmpfs','/var/lib/postgresql/data','-p',f'127.0.0.1:{port}:5432','-e','POSTGRES_PASSWORD','postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3'],env=environment,check=True,stdout=subprocess.DEVNULL)
        end = time.monotonic()+45
        while True:
            try:
                admin = psycopg.connect(url('postgres','postgres',admin_password),connect_timeout=2,autocommit=True)
                break
            except psycopg.Error:
                if time.monotonic()>end:
                    raise RuntimeError('Disposable PostgreSQL did not start') from None
                time.sleep(.2)
        with tempfile.TemporaryDirectory(prefix='vibefinance-test-pg-tls-',dir='/tmp') as directory:
            certs=Path(directory)
            ca=certs/'ca.crt'
            extension=certs/'server.ext'
            extension.write_text('subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:postgres.test.local\nbasicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\n')
            commands=[['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=VibeFinance Local Test CA','-addext','basicConstraints=critical,CA:TRUE','-keyout',str(certs/'ca.key'),'-out',str(ca)],['openssl','req','-newkey','rsa:2048','-nodes','-subj','/CN=localhost','-keyout',str(certs/'server.key'),'-out',str(certs/'server.csr')],['openssl','x509','-req','-days','2','-in',str(certs/'server.csr'),'-CA',str(ca),'-CAkey',str(certs/'ca.key'),'-CAcreateserial','-extfile',str(extension),'-out',str(certs/'server.crt')]]
            for command in commands:
                subprocess.run(command,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for name in ('server.crt','server.key'):
                subprocess.run(cli+['exec','-i','--user','root',container,'tee','/var/lib/postgresql/data/'+name],input=(certs/name).read_bytes(),check=True,stdout=subprocess.DEVNULL)
            subprocess.run(cli+['exec','--user','root',container,'chown','postgres:postgres','/var/lib/postgresql/data/server.crt','/var/lib/postgresql/data/server.key'],check=True)
            subprocess.run(cli+['exec','--user','root',container,'chmod','600','/var/lib/postgresql/data/server.key'],check=True)
            with admin:
                admin.execute("ALTER SYSTEM SET ssl_cert_file='server.crt'")
                admin.execute("ALTER SYSTEM SET ssl_key_file='server.key'")
                admin.execute("ALTER SYSTEM SET ssl=on")
                admin.execute('SELECT pg_reload_conf()')
                admin.execute(sql.SQL('CREATE ROLE vfapp LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS').format(sql.Literal(app_password)))
                for role in ('anon','authenticated','service_role'):
                    admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
                for database in ('vfsource','vfrestore','vfbootstrap'):
                    admin.execute(sql.SQL('CREATE DATABASE {} OWNER vfapp').format(sql.Identifier(database)))
            with psycopg.connect(url('vfsource','postgres',admin_password,ca=ca)) as admin:
                assert admin.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0]
                admin.execute('ALTER DEFAULT PRIVILEGES FOR ROLE vfapp IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO anon,authenticated,service_role')
            environment.pop('VIBEFINANCE_ALLOW_INSECURE_LOCAL_DATABASE',None)
            environment.update(VIBEFINANCE_TEST_POSTGRES_URL=url('vfsource','vfapp',app_password,ca=ca),VIBEFINANCE_TEST_POSTGRES_ADMIN_URL=url('vfsource','postgres',admin_password,ca=ca),VIBEFINANCE_TEST_POSTGRES_RESTORE_URL=url('vfrestore','postgres',admin_password,ca=ca),VIBEFINANCE_TEST_POSTGRES_RESTORE_APP_URL=url('vfrestore','vfapp',app_password,ca=ca),VIBEFINANCE_TEST_POSTGRES_BOOTSTRAP_URL=url('vfbootstrap','postgres',admin_password,ca=ca),VIBEFINANCE_DATABASE_URL=url('vfsource','vfapp',app_password,ca=ca),VIBEFINANCE_TEST_POSTGRES_CA_FILE=str(ca),VIBEFINANCE_TEST_POSTGRES_NETWORK=network,VIBEFINANCE_TEST_POSTGRES_CONTAINER=container,VIBEFINANCE_TEST_POSTGRES_CONTAINER_URL=url('vfsource','vfapp',app_password,ca='/run/test-postgres-ca.crt',internal=True))
            paths = sys.argv[1:] or ['tests/test_production_store.py', 'tests/test_production_api.py', 'tests/test_production_backup.py']
            result = subprocess.run([sys.executable,'-m','pytest','-q',*paths],cwd=root,env=environment)
            return result.returncode
    finally:
        subprocess.run(cli+['rm','--force','--volumes',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(cli+['network','rm',network],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, psycopg.Error):
        print(json.dumps({"ok": False, "scope": "disposable_postgres_integration",
                          "error": "Local integration setup failed; check Docker, OpenSSL, optional dependencies and pinned image access. Private database diagnostics were withheld."}))
        result = 1
    raise SystemExit(result)
