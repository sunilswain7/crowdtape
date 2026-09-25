#!/bin/sh
# One-time local setup. Merge drivers cannot be committed - git will not run a driver a
# repository supplies itself, for obvious reasons - so each clone configures it once.
#
# Without this, every `git pull --rebase` collides with the recorder on the generated
# board data, because both sides rewrite the same machine-written JSON.
set -e
git config merge.regen.name "generated board data; resolve by regenerating"
git config merge.regen.driver "cp -f %B %A"
echo "merge driver configured: site/data/*.json now auto-resolves on pull"
