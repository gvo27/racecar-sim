#!/bin/bash
# colcon test + test-result inside the `test` stage. Exit code = test result.
# If /out is mounted, log/ and the xml test results are copied there (CI artifact);
# HOST_UID/HOST_GID (optional) chown them back to the invoking user.
set +e
colcon test --merge-install --event-handlers console_direct+
colcon test-result --verbose
rc=$?
if [ -d /out ]; then
  cp -r log /out/ 2>/dev/null
  find build \( -path '*test_results*' -o -name 'pytest.xml' -o -name '*.xml' \) -type f \
    ! -name package.xml -print0 | tar --null -T - -cf - 2>/dev/null | tar -C /out -xf -
  [ -n "$HOST_UID" ] && chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" /out
fi
exit $rc
