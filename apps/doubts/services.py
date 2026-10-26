"""
Escriptures de `doubts` (substitueixen el `DoubtController` de Firestore; docs/design/postgres-schema.md §2.16-2.17).

Excepcions de domini (cap tupla). La **propietat es comprova aquí** (C1: només el creador o un admin esborren) a més
de la RLS, que ho reforça a la BD. Les cascades són de la BD: esborrar un dubte esborra totes les seves respostes i
esborrar una resposta, tot el seu subarbre, amb **un sol `DELETE`**. El pare d'una resposta ha de ser del mateix
dubte: ho comprova el service (404) i ho garanteix la FK composta `answers_parent_same_doubt_fk`.
"""
from typing import Optional

from apps.refuges import selectors as refuge_selectors

from . import selectors
from .models import Answer, Doubt


class RefugeNotFound(Exception):
    """El refugi no existeix (inclou un ID que no és UUID)."""


class DoubtNotFound(Exception):
    """El dubte no existeix (inclou un ID que no és UUID)."""


class AnswerNotFound(Exception):
    """La resposta (o la resposta pare) no existeix o és d'un altre dubte."""


class NotOwner(Exception):
    """Qui ho demana no és el creador ni admin."""


def create_doubt(*, refuge_id, creator_uid: str, message: str) -> Doubt:
    """Crea un dubte (2 consultes: existència del refugi + `INSERT … RETURNING`); `created_at` el posa la BD."""
    pk = selectors.parse_id(refuge_id)
    if pk is None or not refuge_selectors.refuge_exists(pk):
        raise RefugeNotFound('Refuge not found')
    doubt = Doubt.objects.create(refuge_id=pk, creator_id=creator_uid, message=message)
    doubt.answers_count = 0                                   # acabat de crear: encara sense respostes
    return doubt


def create_answer(*, doubt_id, creator_uid: str, message: str, parent_answer_id=None) -> Answer:
    """Crea una resposta directa al dubte o una rèplica a `parent_answer_id` (que ha de ser del mateix dubte)."""
    doubt = selectors.get_doubt(doubt_id)
    if doubt is None:
        raise DoubtNotFound('Doubt not found')
    parent = None
    if parent_answer_id is not None:
        parent = selectors.get_answer(doubt.pk, parent_answer_id)
        if parent is None:
            raise AnswerNotFound('Parent answer not found')
    return Answer.objects.create(doubt_id=doubt.pk, creator_id=creator_uid, message=message,
                                 parent_answer_id=parent.pk if parent else None)


def _check_owner(creator_uid: str, actor_uid: Optional[str], is_admin: bool) -> None:
    if not is_admin and (not actor_uid or creator_uid != actor_uid):
        raise NotOwner('No ets el creador')


def delete_doubt(*, doubt_id, actor_uid: Optional[str], is_admin: bool = False) -> None:
    """Esborra el dubte (la BD n'esborra les respostes): 1 consulta de lectura + 1 `DELETE`."""
    doubt = selectors.get_doubt(doubt_id)
    if doubt is None:
        raise DoubtNotFound('Doubt not found')
    _check_owner(doubt.creator_id, actor_uid, is_admin)
    deleted, _ = Doubt.objects.filter(pk=doubt.pk).delete()
    if not deleted:                                           # esborrat concurrent
        raise DoubtNotFound('Doubt not found')


def delete_answer(*, doubt_id, answer_id, actor_uid: Optional[str], is_admin: bool = False) -> None:
    """
    Esborra la resposta i tot el seu subarbre (la BD, per la FK composta): només el creador **de la resposta** o un
    admin (el creador del dubte no pot esborrar respostes alienes). L'`answer_id` ha de ser del `doubt_id` de la URL.
    """
    answer = selectors.get_answer(doubt_id, answer_id)
    if answer is None:
        raise (AnswerNotFound('Answer not found') if selectors.get_doubt(doubt_id) is not None
               else DoubtNotFound('Doubt not found'))
    _check_owner(answer.creator_id, actor_uid, is_admin)
    deleted, _ = Answer.objects.filter(pk=answer.pk).delete()
    if not deleted:                                           # esborrat concurrent (p. ex. d'un avantpassat)
        raise AnswerNotFound('Answer not found')
