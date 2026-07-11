"""Shared rate limiter instance.

In-memory storage — fine for a single-server deployment (the only
topology this project supports today). If LearnStack ever runs multiple
API replicas behind a load balancer, this needs a shared backend (Redis)
or each replica enforces its own independent limit.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
