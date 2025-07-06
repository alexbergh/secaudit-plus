def run_checks(profile: dict, modules_filter: list = None) -> list:
    results = []
    for check in profile['checks']:
        module = check.get("module", "core")
        if modules_filter and module not in modules_filter:
            continue

        cmd = check["command"]
        expected = check.get("expect", "")
        assert_type = check.get("assert_type", "exact")
        severity = check.get("severity", "low")

        output = run_bash(cmd)
        status = assert_output(output, expected, assert_type)

        results.append({
            "id": check["id"],
            "name": check["name"],
            "module": module,
            "result": status,
            "output": output,
            "severity": severity
        })
    return results
