"""Shared local/container launcher and startup preflight."""
import argparse
import logging
import socket

from .application import create_app
from .settings import Settings


def check_port(settings: Settings):
    addresses = socket.getaddrinfo(settings.host, settings.port, type=socket.SOCK_STREAM)
    for family, socktype, protocol, _, address in addresses:
        with socket.socket(family, socktype, protocol) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(address)
            except OSError as exc:
                raise RuntimeError(f"Cannot start on {settings.host}:{settings.port}: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description="Run the FAIR HDF5 Design Suite")
    parser.add_argument("--check", action="store_true", help="Validate configuration, dependencies, storage and port, then exit")
    args = parser.parse_args()
    settings = Settings()
    logging.basicConfig(level="DEBUG" if settings.log_level == "trace" else settings.log_level.upper())
    app = create_app(settings)
    check_port(settings)
    if args.check:
        return
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)


if __name__ == "__main__":
    main()
