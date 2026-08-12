import json
import sqlite3
from uuid import UUID, uuid4

from agentctl.domain import PrecedenceChain, Source
from agentctl.utils import logger


class SqlitePrecedenceChainRepository:
    """Cache keyed by (source, project_id); never the source of truth (SPECS §9)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(self, chain: PrecedenceChain) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM precedence_chains WHERE source = ? AND project_id IS ?",
                (
                    chain.source.value,
                    str(chain.project_id) if chain.project_id else None,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO precedence_chains (id, source, project_id, layers)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    chain.source.value,
                    str(chain.project_id) if chain.project_id else None,
                    json.dumps([
                        layer.model_dump(mode="json") for layer in chain.layers
                    ]),
                ),
            )
        logger.info(
            f"Upserted precedence chain for source {chain.source.value} "
            f"(project {chain.project_id})"
        )

    def get(self, source: Source, project_id: UUID | None) -> PrecedenceChain | None:
        row = self._connection.execute(
            "SELECT * FROM precedence_chains WHERE source = ? AND project_id IS ?",
            (source.value, str(project_id) if project_id else None),
        ).fetchone()
        return self._row_to_model(row) if row else None

    def list(self) -> list[PrecedenceChain]:
        rows = self._connection.execute("SELECT * FROM precedence_chains").fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete(self, source: Source, project_id: UUID | None) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM precedence_chains WHERE source = ? AND project_id IS ?",
                (source.value, str(project_id) if project_id else None),
            )
        logger.info(
            f"Deleted precedence chain for source {source.value} (project {project_id})"
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> PrecedenceChain:
        return PrecedenceChain.model_validate({
            **dict(row),
            "layers": json.loads(row["layers"]),
        })
