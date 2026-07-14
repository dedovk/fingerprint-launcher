from threading import Timer

from core.action_runner import ActionRunner, ActionStatus, ErrorPolicy
from core.execution import CancellationToken


def _command(command_type: str, data: dict | None = None, *, enabled: bool = True):
    return {
        "command_type": command_type,
        "command_data": data or {},
        "enabled": enabled,
    }


def test_runner_executes_actions_in_order_and_reports_success():
    executed = []
    results = []

    def executor(command, _context):
        executed.append(command["command_type"])

    runner = ActionRunner(executor=executor, on_result=results.append)
    report = runner.run([
        _command("lock_screen"),
        _command("open_url", {"url": "https://example.com"}),
    ])

    assert executed == ["lock_screen", "open_url"]
    assert [result.status for result in report.results] == [
        ActionStatus.SUCCESS,
        ActionStatus.SUCCESS,
    ]
    assert results == list(report.results)
    assert report.successful


def test_continue_policy_runs_next_action_after_failure():
    executed = []

    def executor(command, _context):
        executed.append(command["command_type"])
        if command["command_type"] == "lock_screen":
            raise RuntimeError("failed")

    report = ActionRunner(
        executor=executor,
        error_policy=ErrorPolicy.CONTINUE,
    ).run([_command("lock_screen"), _command("sleep")])

    assert executed == ["lock_screen", "sleep"]
    assert [result.status for result in report.results] == [
        ActionStatus.FAILED,
        ActionStatus.SUCCESS,
    ]
    assert report.status == ActionStatus.FAILED


def test_stop_policy_stops_after_failure():
    def executor(_command, _context):
        raise RuntimeError("failed")

    report = ActionRunner(
        executor=executor,
        error_policy=ErrorPolicy.STOP,
    ).run([_command("lock_screen"), _command("sleep")])

    assert len(report.results) == 1
    assert report.results[0].status == ActionStatus.FAILED


def test_disabled_action_is_skipped():
    report = ActionRunner(executor=lambda *_: None).run([
        _command("sleep", enabled=False),
    ])

    assert report.status == ActionStatus.SKIPPED
    assert report.results[0].status == ActionStatus.SKIPPED


def test_before_and_after_delays_wrap_execution():
    events = []
    runner = ActionRunner(executor=lambda *_: events.append("execute"))
    runner.context.sleep = lambda seconds: events.append(seconds)

    runner.run([
        _command("sleep", {"delay_before": 1.5, "delay_after": 2.0}),
    ])

    assert events == [1.5, "execute", 2.0]


def test_cancellation_interrupts_a_long_running_handler():
    token = CancellationToken()

    def long_handler(_command, context):
        context.sleep(10)

    runner = ActionRunner(token=token, executor=long_handler)
    timer = Timer(0.02, runner.cancel)
    timer.start()
    report = runner.run([_command("sleep")])
    timer.join()

    assert report.status == ActionStatus.CANCELLED
    assert report.results[0].status == ActionStatus.CANCELLED


def test_invalid_and_unknown_actions_return_failed_results():
    report = ActionRunner(executor=lambda *_: None).run([
        _command("open_url", {}),
        _command("unknown", {}),
    ])

    assert [result.status for result in report.results] == [
        ActionStatus.FAILED,
        ActionStatus.FAILED,
    ]
