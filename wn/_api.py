
from typing import List

import wn
from wn._models import Word, Synset, Sense
from wn import _store


def word(id: str, lexicon: str = None) -> Word:
    words = _store.find_entries(id=id, lexicon=lexicon)
    if not words:
        raise wn.Error(f'no such lexical entry: {id}')
    return words[0]


def words(form: str = None,
          pos: str = None,
          lgcode: str = None,
          lexicon: str = None) -> List[Word]:
    return _store.find_entries(form=form, pos=pos, lgcode=lgcode, lexicon=lexicon)


def synset(id: str, lexicon: str = None) -> Synset:
    synsets = _store.find_synsets(id=id, lexicon=lexicon)
    if not synsets:
        raise wn.Error(f'no such synset: {id}')
    return synsets[0]


def synsets(form: str = None,
            pos: str = None,
            lgcode: str = None,
            lexicon: str = None) -> List[Synset]:
    return _store.find_synsets(form=form, pos=pos, lgcode=lgcode, lexicon=lexicon)


def sense(id: str) -> Sense:
    return _store.get_sense(id)
