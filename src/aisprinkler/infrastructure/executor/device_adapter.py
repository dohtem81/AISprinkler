"""Generic device execution adapter stub."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from aisprinkler.application.ports.executor_port import (
    ExecutionCommand,
    ExecutionReceipt,
    ExecutorPort,
)


class GenericDeviceAdapter(ExecutorPort):
    """Stub adapter – replace with device-specific HTTP/MQTT/GPIO client."""

    async def dispatch(self, command: ExecutionCommand) -> ExecutionReceipt:
        # TODO: implement device-specific protocol (Rachio, Hunter, GPIO, etc.)
        raise NotImplementedError(
            "GenericDeviceAdapter.dispatch() is not yet implemented. "
            "Use a mock in tests."
        )


class NoOpDeviceAdapter(ExecutorPort):
    """No-op adapter for integration tests and dry-run mode."""

    async def dispatch(self, command: ExecutionCommand) -> ExecutionReceipt:
        return ExecutionReceipt(
            adapter_execution_id=str(uuid.uuid4()),
            accepted=True,
            status="success",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            proof={
                "action": command.action.value,
                "duration_minutes": command.final_duration_minutes,
                "noop": True,
            },
        )
