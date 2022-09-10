#!/bin/bash --login
# https://pythonspeed.com/articles/activate-conda-dockerfile/
# The --login ensures the bash configuration is loaded,
# enabling Conda.

# Temporarily disable strict mode and activate conda:
set +euo pipefail
conda activate ManyFEWS

# Re-enable strict mode:
set -euo pipefail

# exec the final command from script parameters:
exec $*
