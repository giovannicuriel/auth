#!/bin/bash

set -e -x

echo Running initialConf.py
# create predefined users and groups
python3 -m auth.initialConf
python3 ./tests/initialConfTest.py
rc=$?; if [[ ${rc} != 0 ]]; then exit ${rc}; fi
echo initialConf.py ok

echo Starting dredd
for file in "./docs/auth.apib" "./docs/crud-api.apib" "./docs/relation.apib" "./docs/report.apib"; do
    dredd --hookfiles "./tests/dredd-hooks/*hook.py" --server "gunicorn auth.webRoutes:app --bind 0.0.0.0:5000" --language python ${file} http://127.0.0.1:5000
done
