from uuid import UUID, uuid4

from sqlalchemy import Connection, RowMapping, delete, insert, select

from agentctl.domain import PrecedenceChain, Source

from ..schema import precedence_chains
from ._transactions import write_in_transaction


class SqlitePrecedenceChainRepository:
    """Cache keyed by (source, project_id); never the source of truth (SPECS §9)."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def upsert(self, chain: PrecedenceChain) -> None:
        project_id = str(chain.project_id) if chain.project_id else None
        write_in_transaction(
            self._connection,
            [
                delete(precedence_chains).where(
                    precedence_chains.c.source == chain.source.value,
                    precedence_chains.c.project_id.is_(project_id),
                ),
                insert(precedence_chains).values(
                    id=str(uuid4()),
                    source=chain.source.value,
                    project_id=project_id,
                    layers=[layer.model_dump(mode="json") for layer in chain.layers],
                ),
            ],
            message=(
                f"Upserted precedence chain for source {chain.source.value} "
                f"(project {chain.project_id})"
            ),
        )

    def get(self, source: Source, project_id: UUID | None) -> PrecedenceChain | None:
        row = (
            self._connection
            .execute(
                select(precedence_chains).where(
                    precedence_chains.c.source == source.value,
                    precedence_chains.c.project_id.is_(
                        str(project_id) if project_id else None
                    ),
                )
            )
            .mappings()
            .fetchone()
        )
        return self._row_to_model(row) if row else None

    def list(self) -> list[PrecedenceChain]:
        rows = self._connection.execute(select(precedence_chains)).mappings().fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete(self, source: Source, project_id: UUID | None) -> None:
        write_in_transaction(
            self._connection,
            [
                delete(precedence_chains).where(
                    precedence_chains.c.source == source.value,
                    precedence_chains.c.project_id.is_(
                        str(project_id) if project_id else None
                    ),
                )
            ],
            message=(
                f"Deleted precedence chain for source {source.value} "
                f"(project {project_id})"
            ),
        )

    @staticmethod
    def _row_to_model(row: RowMapping) -> PrecedenceChain:
        return PrecedenceChain.model_validate(dict(row))
