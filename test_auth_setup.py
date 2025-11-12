"""
Compatibility shim: tests moved to `api/tests`.

This file remains at the repository root for backwards compatibility.
It delegates execution to `api.tests.test_auth_setup`.
"""

from api.utils import auth_setup_manual_test as _mod


def main():
    # Delegate to the moved test module
    return _mod.main()


if __name__ == '__main__':
    main()
