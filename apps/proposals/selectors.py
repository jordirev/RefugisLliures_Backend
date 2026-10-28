"""
Lectures de `proposals` (substitueixen el DAO de Firestore; docs/design/postgres-schema.md §2.18).

Una consulta per cas d'ús, sense cache; la RLS filtra (cadascú veu les seves; l'admin, totes). El payload i la foto del
refugi són columnes `jsonb`: no cal cap consulta addicional per mostrar-los.
"""
from typing import Optional

from apps.refuges.selectors import parse_refuge_id

from .models import RefugeProposal


def list_proposals(*, status: Optional[str] = None, refuge_id=None, creator_uid: Optional[str] = None) -> list:
    """
    Propostes per `(created_at DESC, id DESC)` (1 consulta; índexs parcials del disseny). Filtres opcionals per estat,
    refugi (un ID que no és UUID no pot coincidir amb cap: llista buida) i creador.
    """
    queryset = RefugeProposal.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if refuge_id is not None:
        pk = parse_refuge_id(refuge_id)
        if pk is None:
            return []
        queryset = queryset.filter(refuge_id=pk)
    if creator_uid:
        queryset = queryset.filter(creator_id=creator_uid)
    return list(queryset.order_by('-created_at', '-id'))


def get_proposal(proposal_id) -> Optional[RefugeProposal]:
    """La proposta o `None` (inexistent, invisible per a l'actor per la RLS o ID que no és un UUID)."""
    pk = parse_refuge_id(proposal_id)
    if pk is None:
        return None
    return RefugeProposal.objects.filter(pk=pk).first()
