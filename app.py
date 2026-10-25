"""Compatibility entry point for `python app.py` and `uvicorn app:app`."""

from fair_hdf5.application import create_app

if __name__ == "__main__":
    from fair_hdf5.__main__ import main

    main()
else:
    app = create_app()
