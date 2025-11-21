#!/usr/bin/env python3
"""Top-level CLI wrapper for ParcVis.

This simple entrypoint calls the `parse()` function in `process_image.py` so
you can run the tool as:

    python main.py -n /path/to/nifti.nii.gz [options]

Or after making it executable:

    chmod +x main.py
    ./main.py -n /path/to/nifti.nii.gz

It purposely delegates to the existing parser to keep behavior identical.
"""

import sys

from process_image import parse


def main(argv=None):
    if argv is not None:
        sys.argv[:] = [sys.argv[0]] + list(argv)
    return parse()


if __name__ == "__main__":
    sys.exit(main())
