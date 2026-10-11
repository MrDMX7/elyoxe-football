"""2026-10-11: the laptop's IPv6 stopped answering; Python tries CloudFront's 8 IPv6 addresses first, 30 s each, so pushplayers
and pushtransfers hit the journal's 5-minute limit (exit 124) while curl (happy eyeballs) was fine. ipv4first puts the IPv4
answers first and keeps IPv6 as the fallback."""
import socket

import ipv4first


def test_ipv4_answers_come_first_and_ipv6_stays():
    six = (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2600::1", 443, 0, 0))
    four = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("108.139.74.166", 443))
    assert ipv4first.order([six, four, six]) == [four, six, six]


def test_installing_twice_wraps_once():
    ipv4first.install(); first = socket.getaddrinfo
    ipv4first.install()
    assert socket.getaddrinfo is first
