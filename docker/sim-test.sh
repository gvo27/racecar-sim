#!/bin/bash
# colcon test + test-result inside the `test` stage. Exit code = test result.
# Discovery is limited to src/: /ws/pkgxml holds copies of each package.xml for the runtime
# stage, and colcon stops with "Duplicate package names" if it sees them.
# Only the rccar_sim_* packages are tested. The car CI tests the car packages.
# The script fails if colcon test fails, if a test fails, if no test ran or if a test skipped.
# If /out is mounted, log/ and the xml test results are copied there (CI artifact);
# HOST_UID/HOST_GID (optional) chown them back to the invoking user.
set +e
colcon test --merge-install --base-paths src --packages-select-regex '^rccar_sim_' \
  --event-handlers console_direct+
rc_test=$?
summary=$(colcon test-result --verbose)
rc=$?
echo "$summary"
if [ "$rc_test" -ne 0 ]; then
  echo "ERROR: colcon test failed (exit $rc_test)"
  rc=1
fi
if echo "$summary" | grep -q '^Summary: 0 tests'; then
  echo "ERROR: no test ran"
  rc=1
fi
# A skip hides a parity gate (golden, drift: car repo or g++ missing). SIM_TEST_ALLOW_SKIP=1 permits it.
if [ "${SIM_TEST_ALLOW_SKIP:-0}" != "1" ] && ! echo "$summary" | grep -q '^Summary: .* 0 skipped'; then
  echo "ERROR: a test skipped (set SIM_TEST_ALLOW_SKIP=1 to permit)"
  rc=1
fi
if [ -d /out ]; then
  cp -r log /out/ 2>/dev/null
  find build \( -path '*test_results*' -o -name 'pytest.xml' -o -name '*.xml' \) -type f \
    ! -name package.xml -print0 | tar --null -T - -cf - 2>/dev/null | tar -C /out -xf -
  [ -n "$HOST_UID" ] && chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" /out
fi
exit $rc
