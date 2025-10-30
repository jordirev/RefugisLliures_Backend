"""
Compatibility shim: tests moved to `api/tests`.

This file remains at the repository root for backwards compatibility.
It delegates execution to `api.tests.test_auth_setup`.
"""

from api.tests import test_auth_setup as _mod


def main():
    # Delegate to the moved test module
    return _mod.main()


if __name__ == '__main__':
    main()
