
r"""Information Content"""

from typing import (
    Callable, Optional, Iterator, Iterable, Dict, List, Tuple, Set, TextIO
)
from pathlib import Path
from collections import Counter
from math import log

from wn._types import AnyPath
from wn._core import Synset, Wordnet
from wn.constants import NOUN, VERB, ADJ, ADV, ADJ_SAT
from wn.util import synset_id_formatter


# Just use a subset of all available parts of speech
IC_PARTS_OF_SPEECH = frozenset((NOUN, VERB, ADJ, ADV))
Freq = Dict[str, Dict[Optional[Synset], float]]


def information_content(synset: Synset, freq: Freq) -> float:
    """Calculate the Information Content value for a synset."""
    return -log(synset_probability(synset, freq))


def synset_probability(synset: Synset, freq: Freq) -> float:
    """Calculate the synset probability."""
    pos = synset.pos
    return freq[pos][synset] / freq[pos][None]


def _initialize(
    wordnet: Wordnet,
    smoothing: float = 0.0,
) -> Freq:
    """Populate an Information Content weight mapping to a smoothing value.

    All synsets in *wordnet* are inserted into the dictionary and
    mapped to *smoothing*.

    """
    freq: Freq = {
        pos: {synset: smoothing for synset in wordnet.synsets(pos=pos)}
        for pos in IC_PARTS_OF_SPEECH
    }
    # pretend ADJ_SAT is just ADJ
    for synset in wordnet.synsets(pos=ADJ_SAT):
        freq[ADJ][synset] = smoothing
    # also initialize totals (when synset is None) for each part-of-speech
    for pos in IC_PARTS_OF_SPEECH:
        freq[pos][None] = smoothing
    return freq


def compute(
    corpus: Iterable[str],
    wordnet: Wordnet,
    distribute_weight: bool = True,
    smoothing: float = 0.0
) -> Freq:
    """Compute Information Content weights from a corpus.

    Arguments:
        corpus: An iterable of string tokens. This is a flat list of
            words and the order does not matter. Tokens may be single
            words or multiple words separated by a space.

        wordnet: An instantiated :class:`wn.Wordnet` object, used to
            look up synsets from words.

        distribute_weight: If :python:`True`, the counts for a word
            are divided evenly among all synsets for the word.

        smoothing: The initial value given to each synset.

    Example:
        >>> import wn, wn.ic, wn.morphy
        >>> ewn = wn.Wordnet('ewn:2020', lemmatizer=wn.morphy.morphy)
        >>> freq = wn.ic.compute(["Dogs", "run", ".", "Cats", "sleep", "."], ewn)
        >>> dog = ewn.synsets('dog', pos='n')[0]
        >>> cat = ewn.synsets('cat', pos='n')[0]
        >>> frog = ewn.synsets('frog', pos='n')[0]
        >>> freq['n'][dog]
        1.125
        >>> freq['n'][cat]
        1.1
        >>> freq['n'][frog]  # no occurrence; smoothing value only
        1.0
        >>> ancestor = dog.lowest_common_hypernyms(cat)[0]  # 'carnivore'
        >>> freq['n'][ancestor]
        1.3250000000000002
    """
    freq = _initialize(wordnet, smoothing=smoothing)
    counts = Counter(corpus)

    hypernym_cache: Dict[Synset, List[Synset]] = {}
    for word, count in counts.items():
        synsets = wordnet.synsets(word)
        num = len(synsets)
        if num == 0:
            continue

        weight = float(count / num if distribute_weight else count)

        for synset in synsets:
            pos = synset.pos
            if pos == ADJ_SAT:
                pos = ADJ
            if pos not in IC_PARTS_OF_SPEECH:
                continue

            freq[pos][None] += weight

            # The following while-loop is equivalent to:
            #
            # freq[pos][synset] += weight
            # for path in synset.hypernym_paths():
            #     for ss in path:
            #         freq[pos][ss] += weight
            #
            # ...but it caches hypernym lookups for speed

            agenda: List[Tuple[Synset, Set[Synset]]] = [(synset, set())]
            while agenda:
                ss, seen = agenda.pop()

                # avoid cycles
                if ss in seen:
                    continue

                freq[pos][ss] += weight

                if ss not in hypernym_cache:
                    hypernym_cache[ss] = ss.hypernyms()
                agenda.extend((hyp, seen | {ss}) for hyp in hypernym_cache[ss])

    return freq


def load(
    source: AnyPath,
    wordnet: Wordnet,
    get_synset_id: Optional[Callable] = None,
) -> Freq:
    """Load an Information Content mapping from a file.

    The *source* argument is a path to an Information Content (IC)
    file as used by the WordNet::Similarity Perl module or the
    NLTK. The *wordnet* argument is a :class:`wn.Wordnet` instance
    **with synset identifiers matching the offsets in the IC file**. A
    :class:`wn.Error` is raised if *wordnet* does not have exactly one
    lexicon.

    The *get_synset_id* argument should be a callable that returns a
    valid synset ID when called as follows:

    .. code-block:: python

       get_synset_id(offset=offset, pos=pos)

    The integer ``offset`` and string ``pos`` arguments come from the
    offsets and parts-of-speech parsed from the IC file. If
    *get_synset_id* is :python:`None`, a default function is created
    with :func:`wn.util.synset_id_formatter` as follows:

    .. code-block:: python

       get_synset_id = synset_id_formatter(prefix=wordnet.lexicons()[0].id)

    Example:

        >>> import wn, wn.ic
        >>> pwn = wn.Wordnet('pwn:3.0')
        >>> path = '~/nltk_data/corpora/wordnet_ic/ic-brown.dat'
        >>> freq = wn.ic.load(path, pwn)

    """
    assert len(wordnet.lexicons()) == 1
    lexid = wordnet.lexicons()[0].id
    if get_synset_id is None:
        get_synset_id = synset_id_formatter(prefix=lexid)

    freq = _initialize(wordnet, smoothing=0.0)

    source = Path(source).expanduser()
    with source.open() as icfile:
        for offset, pos, weight, is_root in _parse_ic_file(icfile):
            ssid = get_synset_id(offset=offset, pos=pos)
            synset = wordnet.synset(ssid)
            freq[pos][synset] = weight
            if is_root:
                freq[pos][None] += weight
    return freq


def _parse_ic_file(icfile: TextIO) -> Iterator[Tuple[int, str, float, bool]]:
    """Parse the Information Content file.

    A sample of the format is::

        wnver::eOS9lXC6GvMWznF1wkZofDdtbBU
        1740n 1915712 ROOT
        1930n 859272
        2137n 1055337

    """
    next(icfile)  # skip header
    for line in icfile:
        ssinfo, value, *isroot = line.split()
        yield (int(ssinfo[:-1]),
               ssinfo[-1],
               float(value),
               bool(isroot))
