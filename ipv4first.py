"""IPv4 before IPv6 for the laptop's jobs (2026-10-11: the laptop's IPv6 stopped answering; Python tries CloudFront's 8 IPv6
addresses first, 30 s each, so pushplayers and pushtransfers hit the journal's 5-minute limit while curl was fine). install()
wraps socket.getaddrinfo once: the IPv4 answers first, IPv6 kept as the fallback. Never imported by the Lambdas."""
import socket

_orig = None


def order(infos):
    return sorted(infos, key=lambda a: a[0] != socket.AF_INET)


def install():
    global _orig
    if _orig is not None:
        return
    _orig = socket.getaddrinfo
    socket.getaddrinfo = lambda *a, **k: order(_orig(*a, **k))
