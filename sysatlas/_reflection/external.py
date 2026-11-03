"""Which imports mean "the system talks to something outside itself".

A fixed, ordered lookup from a top-level import name to a kind of external
system. Names not in the table are reported as plain libraries. Pure data plus
two small functions; no I/O.
"""
from __future__ import annotations

import sys

_SYSTEMS: dict[str, tuple[str, str]] = {
    # datastore
    "sqlalchemy": ("datastore", "SQL database (SQLAlchemy)"),
    "sqlmodel": ("datastore", "SQL database (SQLModel)"),
    "psycopg": ("datastore", "PostgreSQL"),
    "psycopg2": ("datastore", "PostgreSQL"),
    "asyncpg": ("datastore", "PostgreSQL"),
    "pymysql": ("datastore", "MySQL"),
    "MySQLdb": ("datastore", "MySQL"),
    "sqlite3": ("datastore", "SQLite"),
    "pymongo": ("datastore", "MongoDB"),
    "motor": ("datastore", "MongoDB"),
    "redis": ("datastore", "Redis"),
    "peewee": ("datastore", "SQL database (peewee)"),
    "tortoise": ("datastore", "SQL database (Tortoise)"),
    "chromadb": ("datastore", "vector store (Chroma)"),
    "neo4j": ("datastore", "graph database (Neo4j)"),
    # outbound http
    "requests": ("http-client", "HTTP APIs"),
    "httpx": ("http-client", "HTTP APIs"),
    "aiohttp": ("http-client", "HTTP APIs"),
    "urllib3": ("http-client", "HTTP APIs"),
    # inbound http / web frameworks
    "fastapi": ("web-framework", "HTTP server (FastAPI)"),
    "flask": ("web-framework", "HTTP server (Flask)"),
    "django": ("web-framework", "HTTP server (Django)"),
    "starlette": ("web-framework", "HTTP server (Starlette)"),
    "tornado": ("web-framework", "HTTP server (Tornado)"),
    "uvicorn": ("web-framework", "HTTP server (uvicorn)"),
    # cloud
    "boto3": ("cloud", "AWS"),
    "botocore": ("cloud", "AWS"),
    "azure": ("cloud", "Azure"),
    # messaging
    "kafka": ("queue", "Kafka"),
    "confluent_kafka": ("queue", "Kafka"),
    "pika": ("queue", "RabbitMQ"),
    "aio_pika": ("queue", "RabbitMQ"),
    "celery": ("queue", "Celery workers"),
    "nats": ("queue", "NATS"),
    "smtplib": ("queue", "SMTP mail"),
    # model APIs
    "openai": ("llm-api", "OpenAI API"),
    "anthropic": ("llm-api", "Anthropic API"),
    # infrastructure and processes
    "docker": ("infra", "Docker"),
    "kubernetes": ("infra", "Kubernetes"),
    "paramiko": ("infra", "SSH"),
    "subprocess": ("process", "child processes"),
    "grpc": ("rpc", "gRPC"),
}

KINDS_AS_ADAPTER = frozenset({"datastore", "http-client", "cloud", "queue", "llm-api", "infra", "rpc"})
"""System kinds whose presence marks a module as an adapter to the outside."""

_LIBRARY = ("library", "")


def classify_external(root: str) -> tuple[str, str]:
    """(kind, label) for a top-level import name; ('library', '') if not a known system."""
    return _SYSTEMS.get(root, _LIBRARY)


def external_roots(raw_imports: list[str], in_tree_tops: set[str]) -> list[str]:
    """Sorted distinct top-level names that are out-of-tree and not plain stdlib.

    A stdlib module stays in the result only when it names an external system
    (sqlite3, smtplib, subprocess).
    """
    stdlib = sys.stdlib_module_names
    out: set[str] = set()
    for name in raw_imports:
        root = name.split(".")[0]
        if not root or root == "__future__" or root in in_tree_tops:
            continue
        if root in stdlib and root not in _SYSTEMS:
            continue
        out.add(root)
    return sorted(out)
